"""No-network actual-source in-band canary contract and fail-closed policy."""
from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from schemarouter import PolicyViolationError
from scripts.research_durable_inband_probe_lease_e1 import DurableInBandProbeLeaseE1
from scripts.research_live_health_model_menu_e1 import (
    build_health_aware_router,
    capture_health_scoped_model_menu,
    execute_health_scoped_host_call,
)
from scripts.research_long_lived_real_open_meteo_e1 import (
    CappedOpenMeteoTransport,
)
from scripts.research_operator_approved_inband_canary_e1 import (
    GEO,
    InBandCanaryCallbacksE1,
    observe_inband_canary_once,
)
from scripts.research_real_qwen_open_meteo_two_hop_e1 import (
    PRINCIPAL,
    USER_REQUESTS,
)


def source_response(request: httpx.Request) -> httpx.Response:
    if request.url.host == "geocoding-api.open-meteo.com":
        assert request.url.path == "/v1/search"
        assert request.url.params["name"] == "Seoul"
        assert request.url.params["countryCode"] == "KR"
        return httpx.Response(200, json={"results": [{
            "id": 1835848, "country_code": "KR",
            "latitude": 37.5665, "longitude": 126.978,
        }]})
    if request.url.host == "api.open-meteo.com":
        assert request.url.path == "/v1/forecast"
        assert request.url.params["current"] == "temperature_2m"
        return httpx.Response(200, json={
            "current": {"time": "2026-10-20T18:00", "temperature_2m": 17.3},
            "current_units": {"temperature_2m": "°C"},
        })
    raise AssertionError("unapproved external source reached")


@pytest.mark.asyncio
async def test_actual_background_monitor_inband_receipts_and_two_native_calls():
    seen = []

    def observe(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.host)
        return source_response(request)

    receipt = await observe_inband_canary_once(
        approved_public_business_canaries=True,
        transport_factory=lambda: httpx.MockTransport(observe),
    )
    assert receipt["status"] == "success"
    assert receipt["observed_native_calls_completed"] == 2
    assert receipt["actual_https_get_attempts"] == 4
    assert receipt["actual_inband_canary_attempts_by_endpoint"] == {
        "geocoding": 1, "forecast": 1,
    }
    assert receipt["actual_get_attempts_by_endpoint"] == {
        "geocoding": 2, "forecast": 2,
    }
    assert sorted(seen) == sorted([
        "geocoding-api.open-meteo.com",
        "api.open-meteo.com",
        "geocoding-api.open-meteo.com",
        "api.open-meteo.com",
    ])
    for key in (
        "independent_dedicated_health_endpoint_verified",
        "long_term_availability_verified",
        "model_selected_routes",
        "independent_e2_qualified",
        "production_default_changed",
    ):
        assert receipt[key] is False
    assert receipt["model_generations"] == 0
    assert receipt["canary_uses_actual_business_endpoint"] is True
    data = json.dumps(receipt, ensure_ascii=False)
    for forbidden in (
        "Seoul", "37.5665", "126.978", "17.3", "results", "PRIVATE",
        "https://",
    ):
        assert forbidden not in data


@pytest.mark.asyncio
async def test_real_canary_timeout_blocks_native_business_calls_without_retry():
    seen = []

    def timeout(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.host)
        if request.url.host == "geocoding-api.open-meteo.com":
            raise httpx.ConnectTimeout("PRIVATE_CANARY_NET_ERROR", request=request)
        return source_response(request)

    receipt = await observe_inband_canary_once(
        approved_public_business_canaries=True,
        transport_factory=lambda: httpx.MockTransport(timeout),
    )
    assert receipt["status"] == "inband_canary_unhealthy"
    assert receipt["observed_native_calls_completed"] == 0
    assert receipt["actual_https_get_attempts"] == 2
    assert receipt["actual_inband_canary_attempts_by_endpoint"] == {
        "geocoding": 1, "forecast": 1,
    }
    assert len(seen) == 2
    assert "PRIVATE_" not in json.dumps(receipt)


@pytest.mark.asyncio
async def test_actual_native_canary_callback_recovers_after_timeout_then_expires():
    """Real original invoker/health receipts: network down then healthy canary."""
    hits = {"geocode": 0}

    def flaky(request: httpx.Request) -> httpx.Response:
        if request.url.host == "geocoding-api.open-meteo.com":
            hits["geocode"] += 1
            if hits["geocode"] == 1:
                raise httpx.ConnectTimeout(
                    "PRIVATE_ACTUAL_CANARY_TIMEOUT", request=request,
                )
        return source_response(request)

    transport = CappedOpenMeteoTransport(
        httpx.MockTransport(flaky), max_requests=6,
    )
    async with httpx.AsyncClient(
        transport=transport, follow_redirects=False,
    ) as client:
        probes = InBandCanaryCallbacksE1(
            client, approved_public_business_canaries=True,
            attempts_per_route=2,
        )
        router = build_health_aware_router(
            client, trusted_health_probes={
                GEO: probes.geocoding,
                "open_meteo_weather.current": probes.forecast,
            },
            transport_retry_budget=0,
        )
        try:
            await router.check_health_once()
            unavailable = capture_health_scoped_model_menu(
                router, USER_REQUESTS["en"], principal=PRINCIPAL,
                host_request_inputs={
                    "name": "Seoul", "language": "en", "country_code": "KR",
                },
            )
            assert unavailable.route_ids == ()
            assert unavailable.status == "temporary_unavailable"
            assert transport.total_requests == 2

            # The SAME host-approved source callback is invoked a second
            # time, and a genuinely new HTTP result verifies recovery.
            await router.check_health_once()
            recovered = capture_health_scoped_model_menu(
                router, USER_REQUESTS["en"], principal=PRINCIPAL,
                host_request_inputs={
                    "name": "Seoul", "language": "en", "country_code": "KR",
                },
            )
            assert recovered.route_ids == (GEO,)
            location = await execute_health_scoped_host_call(
                recovered, route_id=GEO,
                arguments={
                    "name": "Seoul", "language": "en", "country_code": "KR",
                },
                host_required_output_fields=(
                    "location_id", "latitude", "longitude", "country_code",
                ),
            )
            second = capture_health_scoped_model_menu(
                router, USER_REQUESTS["en"], principal=PRINCIPAL,
                host_request_inputs={
                    "name": "Seoul", "language": "en", "country_code": "KR",
                },
                prior_public_observation=location,
                executed_route_ids=(GEO,),
            )
            result = await execute_health_scoped_host_call(
                second, route_id="open_meteo_weather.current",
                arguments={
                    "latitude": location["latitude"],
                    "longitude": location["longitude"],
                },
                host_required_output_fields=(
                    "time", "temperature_2m", "temperature_unit",
                ),
            )
            assert result["status"] == "ok"
            assert transport.total_requests == 6
            assert probes.counts[GEO] == 2

            # Budget exhausted: a later check MUST NOT recycle stale
            # Healthy; it fails closed without a seventh provider GET.
            await router.check_health_once()
            with pytest.raises(PolicyViolationError, match="availability changed"):
                recovered.assert_current()
            assert transport.total_requests == 6
        finally:
            await router.aclose()


@pytest.mark.asyncio
async def test_forecast_canary_500_is_not_interpreted_as_healthy():
    def error(request: httpx.Request) -> httpx.Response:
        if request.url.host == "api.open-meteo.com":
            return httpx.Response(503, json={"reason": "PRIVATE_REMOTE_FAILURE"})
        return source_response(request)

    receipt = await observe_inband_canary_once(
        approved_public_business_canaries=True,
        transport_factory=lambda: httpx.MockTransport(error),
    )
    assert receipt["status"] == "inband_canary_unhealthy"
    assert receipt["observed_native_calls_completed"] == 0
    assert receipt["actual_https_get_attempts"] == 2
    assert "PRIVATE_" not in json.dumps(receipt)


@pytest.mark.asyncio
async def test_malformed_geocoder_canary_response_is_not_healthy():
    def malformed(request: httpx.Request) -> httpx.Response:
        if request.url.host == "geocoding-api.open-meteo.com":
            return httpx.Response(200, json={"results": []})
        return source_response(request)

    receipt = await observe_inband_canary_once(
        approved_public_business_canaries=True,
        transport_factory=lambda: httpx.MockTransport(malformed),
    )
    assert receipt["status"] == "inband_canary_unhealthy"
    assert receipt["observed_native_calls_completed"] == 0


@pytest.mark.asyncio
async def test_real_host_runner_consumes_shared_lease_across_sessions(tmp_path: Path):
    """No-network original source runner, persisted per-route approval."""
    lease_file = tmp_path / "bounded-approved.sqlite3"
    lease = DurableInBandProbeLeaseE1(lease_file)
    lease.initialize(
        operator_approved=True, validity_seconds=300, attempts_per_route=1,
    )
    calls = {"http_get": 0}

    def counted(request: httpx.Request) -> httpx.Response:
        calls["http_get"] += 1
        return source_response(request)

    def factory() -> httpx.AsyncBaseTransport:
        return httpx.MockTransport(counted)

    first = await observe_inband_canary_once(
        approved_public_business_canaries=True,
        transport_factory=factory,
        existing_shared_lease_file=lease_file,
    )
    assert first["status"] == "success"
    assert first["actual_https_get_attempts"] == 4
    assert first["durable_shared_lease_enabled"] is True
    assert first["durable_shared_lease_spent_by_route"] == {
        "geocoding": 1, "forecast": 1,
    }
    # Restart the ORIGINAL host runner with new callback/router objects:
    # reusing its existing lease MUST NOT authorize even one new canary GET.
    next_session = await observe_inband_canary_once(
        approved_public_business_canaries=True,
        transport_factory=factory,
        existing_shared_lease_file=lease_file,
    )
    assert next_session["status"] == "inband_canary_unhealthy"
    assert next_session["actual_https_get_attempts"] == 0
    assert next_session["actual_inband_canary_attempts_by_endpoint"] == {
        "geocoding": 0, "forecast": 0,
    }
    assert next_session["durable_shared_lease_spent_by_route"] == {
        "geocoding": 1, "forecast": 1,
    }
    assert calls["http_get"] == 4
    for receipt in (first, next_session):
        redacted = json.dumps(receipt)
        assert str(lease_file) not in redacted
        assert "PRIVATE_" not in redacted


@pytest.mark.asyncio
async def test_no_or_revoked_durable_lease_never_hits_provider(tmp_path: Path):
    lease_file = tmp_path / "never-approved.sqlite3"
    counter = {"get": 0}

    def forbid(request: httpx.Request) -> httpx.Response:
        counter["get"] += 1
        raise AssertionError("unapproved GET")

    def factory() -> httpx.AsyncBaseTransport:
        return httpx.MockTransport(forbid)

    missing = await observe_inband_canary_once(
        approved_public_business_canaries=True,
        transport_factory=factory,
        existing_shared_lease_file=lease_file,
    )
    assert missing["status"] == "inband_canary_unhealthy"
    assert missing["actual_https_get_attempts"] == 0
    assert not lease_file.exists()
    lease = DurableInBandProbeLeaseE1(lease_file)
    lease.initialize(
        operator_approved=True, validity_seconds=300, attempts_per_route=2,
    )
    assert lease.revoke(operator_approved=True) is True
    revoked = await observe_inband_canary_once(
        approved_public_business_canaries=True,
        transport_factory=factory,
        existing_shared_lease_file=lease_file,
    )
    assert revoked["status"] == "inband_canary_unhealthy"
    assert revoked["durable_shared_lease_spent_by_route"] == {
        "geocoding": 0, "forecast": 0,
    }
    assert counter["get"] == 0


@pytest.mark.asyncio
async def test_other_worker_revokes_lease_during_first_native_get(tmp_path: Path):
    """Already exposed weather must disappear before its native business GET.

    The second geocoding request is the original native business request:
    the first was the separately budgeted in-band health canary. A different
    SQLite controller commits revocation during that original GET.
    """
    lease_file = tmp_path / "another-worker-stop.sqlite3"
    issuer = DurableInBandProbeLeaseE1(lease_file)
    issuer.initialize(
        operator_approved=True, validity_seconds=300, attempts_per_route=1,
    )
    separate_worker = DurableInBandProbeLeaseE1(lease_file)
    seen = {"geocoding": 0, "forecast": 0}

    def revoke_at_geocode_result(request: httpx.Request) -> httpx.Response:
        if request.url.host == "geocoding-api.open-meteo.com":
            seen["geocoding"] += 1
            if seen["geocoding"] == 2:
                assert separate_worker.revoke(operator_approved=True) is True
        elif request.url.host == "api.open-meteo.com":
            seen["forecast"] += 1
        return source_response(request)

    receipt = await observe_inband_canary_once(
        approved_public_business_canaries=True,
        existing_shared_lease_file=lease_file,
        transport_factory=lambda: httpx.MockTransport(revoke_at_geocode_result),
    )
    assert receipt["status"] == "source_now_unavailable"
    # A concurrent revoke may invalidate the source completion receipt even
    # though the first HTTP request was already admitted; do not pretend an
    # in-flight source GET can be atomically rolled back.
    assert receipt["observed_native_calls_completed"] in (0, 1)
    assert receipt["actual_https_get_attempts"] == 3
    assert seen == {"geocoding": 2, "forecast": 1}
    assert receipt["durable_shared_lease_spent_by_route"] == {
        "geocoding": 1, "forecast": 1,
    }
    sanitized = json.dumps(receipt)
    assert str(lease_file) not in sanitized
    assert "Seoul" not in sanitized
    assert "PRIVATE_" not in sanitized




@pytest.mark.asyncio
async def test_transport_denies_revocation_between_host_read_and_delegate(tmp_path: Path):
    """The opt-in final transport read prevents a now-revoked business GET."""
    path = tmp_path / "operator-approved.sqlite3"
    lease = DurableInBandProbeLeaseE1(path)
    lease.initialize(
        operator_approved=True, validity_seconds=300, attempts_per_route=1,
    )
    separate = DurableInBandProbeLeaseE1(path)
    outbound = {"count": 0}
    gates = {"count": 0}

    def never_delegate(request: httpx.Request) -> httpx.Response:
        outbound["count"] += 1
        return source_response(request)

    async def revoking_gate() -> bool:
        gates["count"] += 1
        # Earlier host admission was true, but a concurrent operator stop
        # lands just before transport would dispatch the original source GET.
        assert separate.revoke(operator_approved=True) is True
        return lease.approval_active()

    assert lease.approval_active() is True  # initial host-level read
    transport = CappedOpenMeteoTransport(
        httpx.MockTransport(never_delegate),
        source_admission_check=revoking_gate,
    )
    async with httpx.AsyncClient(
        transport=transport, follow_redirects=False,
    ) as client:
        with pytest.raises(RuntimeError, match="approval unavailable"):
            await client.get(
                "https://geocoding-api.open-meteo.com/v1/search",
                params={
                    "name": "Seoul", "language": "en", "countryCode": "KR",
                    "count": 10, "format": "json",
                },
            )
    assert gates["count"] == 1
    assert outbound["count"] == 0
    assert transport.total_requests == 0
    assert lease.public_counts() == {"geocoding": 0, "forecast": 0}


@pytest.mark.asyncio
async def test_transport_optional_lease_read_denies_subsequent_get_without_budget_spend(
    tmp_path: Path,
):
    """Valid GET passes, later revoke forbids future source requests."""
    path = tmp_path / "original-shared-lease.sqlite3"
    lease = DurableInBandProbeLeaseE1(path)
    lease.initialize(
        operator_approved=True, validity_seconds=300, attempts_per_route=1,
    )
    calls = {"count": 0}

    def counted(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return source_response(request)

    async def admission() -> bool:
        return lease.approval_active()

    transport = CappedOpenMeteoTransport(
        httpx.MockTransport(counted),
        source_admission_check=admission,
    )
    async with httpx.AsyncClient(
        transport=transport, follow_redirects=False,
    ) as client:
        url = "https://geocoding-api.open-meteo.com/v1/search"
        params = {
            "name": "Seoul", "language": "en", "countryCode": "KR",
            "count": 10, "format": "json",
        }
        response = await client.get(url, params=params)
        assert response.status_code == 200
        assert lease.revoke(operator_approved=True) is True
        with pytest.raises(RuntimeError, match="approval unavailable"):
            await client.get(url, params=params)
    assert calls["count"] == 1
    assert transport.total_requests == 1
    # Read-only transport authorization is distinct from consuming the
    # bounded health-probe GET budget.
    assert lease.public_counts() == {"geocoding": 0, "forecast": 0}


@pytest.mark.asyncio
async def test_no_approval_cannot_create_outbound_requests():
    seen = []

    def response(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return source_response(request)

    with pytest.raises(ValueError, match="permission"):
        await observe_inband_canary_once(
            approved_public_business_canaries=False,
            transport_factory=lambda: httpx.MockTransport(response),
        )
    assert seen == []


@pytest.mark.asyncio
async def test_exhausted_probe_budget_fails_closed_never_recycles_healthy():
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(source_response),
    ) as client:
        probes = InBandCanaryCallbacksE1(
            client, approved_public_business_canaries=True, attempts_per_route=1,
        )
        assert await probes.geocoding() is True
        assert await probes.geocoding() is False
        assert probes.counts[GEO] == 1


@pytest.mark.parametrize("invalid", (0, 3, -1, True, 1.2))
def test_canary_per_route_budget_is_explicit_and_finite(invalid):
    with pytest.raises(ValueError, match="per-route"):
        InBandCanaryCallbacksE1(
            httpx.AsyncClient(transport=httpx.MockTransport(source_response)),
            approved_public_business_canaries=True,
            attempts_per_route=invalid,
        )


@pytest.mark.asyncio
async def test_invalid_canary_approval_rejected_even_with_good_source():
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(source_response),
    ) as client:
        with pytest.raises(ValueError, match="permission"):
            InBandCanaryCallbacksE1(
                client, approved_public_business_canaries=False,
            )
