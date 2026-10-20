"""Offline SQLite budgets: atomic same-host concurrency and restart fail-closed."""
from __future__ import annotations

import json
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from pathlib import Path

import httpx
import pytest

from schemarouter import PolicyViolationError
from scripts import research_durable_inband_probe_lease_e1 as lease_module
from scripts.research_durable_inband_probe_lease_e1 import (
    DurableInBandProbeLeaseE1,
)
from scripts.research_live_health_model_menu_e1 import (
    GEO,
    WEATHER,
    build_health_aware_router,
    capture_health_scoped_model_menu,
)
from scripts.research_operator_approved_inband_canary_e1 import (
    InBandCanaryCallbacksE1,
)
from scripts.research_real_qwen_open_meteo_two_hop_e1 import (
    PRINCIPAL,
    USER_REQUESTS,
)


def _store(tmp_path: Path) -> DurableInBandProbeLeaseE1:
    return DurableInBandProbeLeaseE1(tmp_path / "operator-approved.sqlite3")


def _approve(store: DurableInBandProbeLeaseE1, *, cap: int = 1) -> None:
    store.initialize(
        operator_approved=True, validity_seconds=300, attempts_per_route=cap,
    )


def _source_response(request: httpx.Request) -> httpx.Response:
    if request.url.host == "geocoding-api.open-meteo.com":
        return httpx.Response(200, json={"results": [{
            "id": 1835848, "country_code": "KR",
            "latitude": 37.5665, "longitude": 126.978,
        }]})
    if request.url.host == "api.open-meteo.com":
        return httpx.Response(200, json={
            "current": {"time": "2026-10-20T19:00", "temperature_2m": 17.0},
            "current_units": {"temperature_2m": "°C"},
        })
    raise AssertionError("unapproved source")


def test_local_shared_lease_claim_is_atomic_across_connections_and_threads(tmp_path):
    first = _store(tmp_path)
    _approve(first, cap=2)
    second = _store(tmp_path)
    def reserve(i: int) -> bool:
        return (first if i % 2 else second).try_claim(GEO)
    with ThreadPoolExecutor(max_workers=8) as pool:
        observed = list(pool.map(reserve, range(24)))
    assert sum(observed) == 2
    assert first.public_counts() == {"geocoding": 2, "forecast": 0}
    assert second.try_claim(GEO) is False
    assert second.try_claim(WEATHER) is True
    assert first.public_counts() == {"geocoding": 2, "forecast": 1}


def _reserve_from_independent_process(path: str) -> bool:
    return DurableInBandProbeLeaseE1(Path(path)).try_claim(GEO)


def test_actual_distinct_linux_processes_observe_same_atomic_limit(tmp_path):
    # Unlike ThreadPoolExecutor, each task runs with an independent process,
    # separately opens SQLite and races on exactly one shared trusted file.
    store = _store(tmp_path)
    _approve(store, cap=2)
    path = str(tmp_path / "operator-approved.sqlite3")
    with ProcessPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(
            _reserve_from_independent_process,
            (path for _ in range(12)),
        ))
    assert sum(results) == 2
    assert store.public_counts() == {"geocoding": 2, "forecast": 0}


def test_revocation_persists_and_cannot_restore_a_spent_lease(tmp_path):
    store = _store(tmp_path)
    _approve(store, cap=2)
    assert store.try_claim(GEO) is True
    assert store.revoke(operator_approved=True) is True
    assert store.revoke(operator_approved=True) is False
    assert store.try_claim(GEO) is False
    assert store.try_claim(WEATHER) is False
    restarted = _store(tmp_path)
    assert restarted.try_claim(GEO) is False
    assert restarted.try_claim(WEATHER) is False
    assert restarted.public_counts() == {"geocoding": 1, "forecast": 0}
    with pytest.raises(ValueError, match="cannot be renewed"):
        restarted.initialize(
            operator_approved=True,
            validity_seconds=300,
            attempts_per_route=2,
        )


def test_revocation_blocks_independent_linux_process_claims(tmp_path):
    store = _store(tmp_path)
    _approve(store, cap=2)
    assert store.revoke(operator_approved=True)
    with ProcessPoolExecutor(max_workers=4) as workers:
        attempts = list(workers.map(
            _reserve_from_independent_process,
            (str(tmp_path / "operator-approved.sqlite3") for _ in range(12)),
        ))
    assert not any(attempts)
    assert store.public_counts() == {"geocoding": 0, "forecast": 0}


def test_operator_must_authorize_revocation_and_corrupt_db_fails_closed(tmp_path):
    store = _store(tmp_path)
    _approve(store)
    with pytest.raises(ValueError, match="operator"):
        store.revoke(operator_approved=False)
    assert store.try_claim(GEO) is True
    corrupted = DurableInBandProbeLeaseE1(tmp_path / "corrupt.sqlite3")
    with pytest.raises(RuntimeError, match="absent"):
        corrupted.revoke(operator_approved=True)
    (tmp_path / "corrupt.sqlite3").write_bytes(b"PRIVATE_SQLITE_CANARY")
    with pytest.raises(RuntimeError, match="revocation failed") as failure:
        corrupted.revoke(operator_approved=True)
    assert "PRIVATE_" not in str(failure.value)
    assert store.try_claim(WEATHER) is True


@pytest.mark.asyncio
async def test_revocation_rechecks_same_router_and_discards_prior_healthy_menu(
    tmp_path,
):
    store = _store(tmp_path)
    _approve(store, cap=2)
    network_attempts = {"count": 0}

    def response(request: httpx.Request) -> httpx.Response:
        network_attempts["count"] += 1
        return _source_response(request)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(response),
    ) as client:
        callbacks = InBandCanaryCallbacksE1(
            client, approved_public_business_canaries=True,
            attempts_per_route=2,
        )
        router = build_health_aware_router(
            client, trusted_health_probes={
                GEO: store.wrap_probe(GEO, callbacks.geocoding),
                WEATHER: store.wrap_probe(WEATHER, callbacks.forecast),
            },
        )
        try:
            await router.check_health_once()
            before = capture_health_scoped_model_menu(
                router, USER_REQUESTS["en"], principal=PRINCIPAL,
                host_request_inputs={
                    "name": "Seoul", "language": "en", "country_code": "KR",
                },
            )
            assert before.route_ids == (GEO,)
            assert network_attempts["count"] == 2
            assert await store.revoke_and_reconcile(
                router, operator_approved=True,
            ) is True
            assert network_attempts["count"] == 2
            after = capture_health_scoped_model_menu(
                router, USER_REQUESTS["en"], principal=PRINCIPAL,
                host_request_inputs={
                    "name": "Seoul", "language": "en", "country_code": "KR",
                },
            )
            assert after.route_ids == ()
            assert after.status == "temporary_unavailable"
            with pytest.raises(PolicyViolationError, match="availability changed"):
                before.assert_current()
            assert store.public_counts() == {"geocoding": 1, "forecast": 1}
        finally:
            await router.aclose()


@pytest.mark.asyncio
async def test_revoke_reconcile_reports_failure_for_unguarded_healthy_router(
    tmp_path,
):
    """Never claim active route was withdrawn if it ignores the lease."""
    store = _store(tmp_path)
    _approve(store)
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(_source_response),
    ) as client:
        router = build_health_aware_router(
            client, trusted_health_probes={
                GEO: lambda: True,
                WEATHER: lambda: True,
            },
        )
        try:
            await router.check_health_once()
            with pytest.raises(RuntimeError, match="did not reflect revoked"):
                await store.revoke_and_reconcile(
                    router, operator_approved=True,
                )
            # The *durable* budget was revoked even though caller supplied a
            # wrong router, so no new approved canary calls can start.
            assert store.try_claim(GEO) is False
            assert store.try_claim(WEATHER) is False
        finally:
            await router.aclose()


@pytest.mark.asyncio
async def test_invalid_router_cannot_trigger_revocation(tmp_path):
    store = _store(tmp_path)
    _approve(store)
    with pytest.raises(ValueError, match="router"):
        await store.revoke_and_reconcile(
            object(), operator_approved=True,  # type: ignore[arg-type]
        )
    assert store.try_claim(GEO) is True


def test_lease_cannot_reset_after_restart_or_reapproval_without_new_path(tmp_path):
    store = _store(tmp_path)
    _approve(store, cap=1)
    assert store.try_claim(GEO) is True
    restarted = _store(tmp_path)
    assert restarted.try_claim(GEO) is False
    with pytest.raises(ValueError, match="cannot be renewed"):
        restarted.initialize(
            operator_approved=True, validity_seconds=3600,
            attempts_per_route=2,
        )
    assert restarted.public_counts() == {"geocoding": 1, "forecast": 0}


def test_missing_or_corrupt_database_must_never_autocreate_healthy(tmp_path):
    store = _store(tmp_path)
    assert store.try_claim(GEO) is False
    assert store.public_counts() == {}
    assert not (tmp_path / "operator-approved.sqlite3").exists()
    (tmp_path / "operator-approved.sqlite3").write_bytes(b"not a sqlite database")
    assert store.try_claim(GEO) is False
    assert store.public_counts() == {}


def test_expiry_and_clock_rollback_fail_closed_without_reissuing_lease(tmp_path, monkeypatch):
    clock = {"seconds": 1000.0}
    monkeypatch.setattr(lease_module, "_utc_seconds", lambda: clock["seconds"])
    store = _store(tmp_path)
    store.initialize(
        operator_approved=True, validity_seconds=10, attempts_per_route=2,
    )
    assert store.try_claim(GEO) is True
    clock["seconds"] = 999.0
    assert store.try_claim(GEO) is False
    clock["seconds"] = 1010.0
    assert store.try_claim(GEO) is False
    assert store.public_counts() == {"geocoding": 1, "forecast": 0}
    with pytest.raises(ValueError, match="cannot be renewed"):
        store.initialize(
            operator_approved=True, validity_seconds=300,
            attempts_per_route=2,
        )


@pytest.mark.parametrize(("duration", "budget"), (
    (0, 1), (-1, 1), (3601, 1), (True, 1), (300, 0), (300, 3),
    (300, True), (300, 1.5),
))
def test_invalid_operator_lease_config_fails_closed(tmp_path, duration, budget):
    store = _store(tmp_path)
    with pytest.raises(ValueError, match="duration|allowance"):
        store.initialize(
            operator_approved=True,
            validity_seconds=duration,
            attempts_per_route=budget,
        )
    assert store.try_claim(GEO) is False


def test_missing_operator_approval_rejected_before_file_creation(tmp_path):
    store = _store(tmp_path)
    with pytest.raises(ValueError, match="operator"):
        store.initialize(
            operator_approved=False, validity_seconds=300,
            attempts_per_route=1,
        )
    assert not (tmp_path / "operator-approved.sqlite3").exists()


@pytest.mark.asyncio
async def test_real_source_canary_callbacks_denied_after_restart_no_network():
    from tempfile import TemporaryDirectory
    with TemporaryDirectory() as d:
        path = Path(d) / "approved.sqlite3"
        store = DurableInBandProbeLeaseE1(path)
        _approve(store, cap=1)
        requests = {"count": 0}

        def mock(request: httpx.Request) -> httpx.Response:
            requests["count"] += 1
            return _source_response(request)

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(mock),
        ) as client:
            originals = InBandCanaryCallbacksE1(
                client, approved_public_business_canaries=True,
            )
            router = build_health_aware_router(
                client, trusted_health_probes={
                    GEO: store.wrap_probe(GEO, originals.geocoding),
                    WEATHER: store.wrap_probe(WEATHER, originals.forecast),
                },
            )
            try:
                await router.check_health_once()
                visible = capture_health_scoped_model_menu(
                    router, USER_REQUESTS["en"], principal=PRINCIPAL,
                    host_request_inputs={
                        "name": "Seoul", "language": "en", "country_code": "KR",
                    },
                )
                assert visible.route_ids == (GEO,)
                assert requests["count"] == 2
            finally:
                await router.aclose()

        # Simulate a new process with a separate controller object. The new
        # router/callback instance MUST NOT recreate/renew old shared budget.
        reopened = DurableInBandProbeLeaseE1(path)
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(mock),
        ) as second_client:
            callbacks = InBandCanaryCallbacksE1(
                second_client, approved_public_business_canaries=True,
            )
            router2 = build_health_aware_router(
                second_client, trusted_health_probes={
                    GEO: reopened.wrap_probe(GEO, callbacks.geocoding),
                    WEATHER: reopened.wrap_probe(WEATHER, callbacks.forecast),
                },
            )
            try:
                await router2.check_health_once()
                hidden = capture_health_scoped_model_menu(
                    router2, USER_REQUESTS["en"], principal=PRINCIPAL,
                    host_request_inputs={
                        "name": "Seoul", "language": "en", "country_code": "KR",
                    },
                )
                assert hidden.status == "temporary_unavailable"
                assert hidden.route_ids == ()
                assert requests["count"] == 2
                assert reopened.public_counts() == {
                    "geocoding": 1, "forecast": 1,
                }
            finally:
                await router2.aclose()


@pytest.mark.asyncio
async def test_failures_spend_tokens_even_when_remote_canary_times_out(tmp_path):
    store = _store(tmp_path)
    _approve(store)
    attempts = {"calls": 0}

    async def bad() -> bool:
        attempts["calls"] += 1
        raise httpx.ConnectTimeout("PRIVATE_PROVIDER_ERROR")

    wrapped = store.wrap_probe(GEO, bad)
    assert await wrapped() is False
    assert await wrapped() is False
    assert attempts["calls"] == 1
    assert store.public_counts()["geocoding"] == 1
    assert "PRIVATE_" not in json.dumps(store.public_counts())


def test_only_original_canary_route_ids_allowed(tmp_path):
    store = _store(tmp_path)
    _approve(store)
    assert store.try_claim("open_meteo_weather.admin") is False
    with pytest.raises(ValueError, match="known authorized"):
        store.wrap_probe("open_meteo_weather.admin", lambda: True)
    assert store.public_counts() == {"geocoding": 0, "forecast": 0}
