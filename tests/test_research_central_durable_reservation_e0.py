"""Synthetic only: durable SQLite reservation, process race and no-GET tests."""
from __future__ import annotations

import sqlite3
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from multiprocessing import get_context
from pathlib import Path

import pytest

from scripts.research_central_durable_reservation_e0 import (
    DurableCentralReservationE0,
)
from scripts.research_central_egress_admission_e0 import (
    SyntheticEgressRequestE0,
)
from scripts.research_live_health_model_menu_e1 import GEO, WEATHER


def _fixture(path: Path, *, cap: int = 2) -> DurableCentralReservationE0:
    store = DurableCentralReservationE0(path)
    store.provision_once(
        allowed={
            ("church", "worker-a", GEO): "geo-revision-1",
            ("church", "worker-b", GEO): "geo-revision-1",
            ("school", "worker-a", GEO): "geo-revision-1",
            ("church", "worker-a", WEATHER): "weather-revision-1",
        },
        cap_per_tenant_route=cap,
    )
    return store


def _request(
    token: str, *, tenant: str = "church", worker: str = "worker-a",
    route: str = GEO, revision: str = "geo-revision-1",
    epoch: int = 1,
) -> SyntheticEgressRequestE0:
    return SyntheticEgressRequestE0(
        tenant=tenant, workload=worker, route_id=route,
        source_fingerprint=revision, request_id=token, epoch=epoch,
    )


def _independent_reserve(path: str, token: str, tenant: str) -> str:
    """Fresh spawned interpreter, own SQLite connection, never a provider."""
    return DurableCentralReservationE0(Path(path)).reserve(
        _request(token, tenant=tenant)
    )


def _independent_revoke(path: str, tenant: str | None) -> bool:
    store = DurableCentralReservationE0(Path(path))
    return store.revoke_all() if tenant is None else store.revoke_tenant(tenant)


def test_restart_cannot_reset_nonrefundable_quota_or_duplicate_idempotency(tmp_path):
    path = tmp_path / "central-reservations.sqlite3"
    first = _fixture(path, cap=1)
    assert first.reserve(_request("one")) == "synthetic_reservation"
    restarted = DurableCentralReservationE0(path)
    assert restarted.reserve(_request("one")) == "duplicate_request"
    assert restarted.reserve(_request("two")) == "allowance_exhausted"
    assert restarted.reserved_for_test("church", GEO) == 1
    with pytest.raises(FileExistsError):
        restarted.provision_once(
            allowed={("church", "worker-a", GEO): "geo-revision-1"},
            cap_per_tenant_route=2,
        )


def test_two_tenants_have_separate_durable_native_route_budgets(tmp_path):
    path = tmp_path / "tenants.sqlite3"
    store = _fixture(path, cap=2)
    for i in range(2):
        assert store.reserve(_request(f"church-{i}")) == "synthetic_reservation"
    assert store.reserve(_request("church-extra")) == "allowance_exhausted"
    for i in range(2):
        assert store.reserve(
            _request(f"school-{i}", tenant="school")
        ) == "synthetic_reservation"
    assert store.reserve(
        _request("school-extra", tenant="school")
    ) == "allowance_exhausted"
    assert store.reserved_for_test("church", GEO) == 2
    assert store.reserved_for_test("school", GEO) == 2
    # Separate native source's quota remains available to the first tenant.
    assert store.reserve(
        _request("weather", route=WEATHER, revision="weather-revision-1")
    ) == "synthetic_reservation"


def test_tenant_revocation_is_durable_without_stopping_other_tenant(tmp_path):
    path = tmp_path / "stop.sqlite3"
    store = _fixture(path)
    assert store.revoke_tenant("church") is True
    assert store.revoke_tenant("church") is False
    restarted = DurableCentralReservationE0(path)
    assert restarted.reserve(_request("church")) == "operator_revoked"
    assert restarted.reserve(
        _request("school", tenant="school")
    ) == "synthetic_reservation"
    assert restarted.revoke_all() is True
    assert restarted.revoke_all() is False
    assert store.reserve(
        _request("school-later", tenant="school", epoch=2)
    ) == "operator_revoked"
    with pytest.raises(ValueError, match="preprovisioned"):
        store.revoke_tenant("no-such-tenant")


def test_untrusted_fixture_drift_and_absent_database_fail_closed(tmp_path):
    missing = DurableCentralReservationE0(tmp_path / "missing.sqlite3")
    assert missing.reserve(_request("one")) == "synthetic_authority_unavailable"
    assert not (tmp_path / "missing.sqlite3").exists()
    path = tmp_path / "scoped.sqlite3"
    store = _fixture(path)
    cases = (
        _request("wrong-worker", worker="unknown"),
        _request("wrong-source", revision="wrong"),
        _request("wrong-epoch", epoch=2),
        _request("wrong-tenant", tenant="unknown"),
    )
    assert [store.reserve(case) for case in cases] == [
        "identity_or_scope_denied",
        "identity_or_scope_denied",
        "stale_epoch",
        "identity_or_scope_denied",
    ]
    malformed = SyntheticEgressRequestE0(
        tenant=[],  # type: ignore[arg-type]
        workload="worker-a", route_id=GEO,
        source_fingerprint="geo-revision-1",
        request_id="malformed", epoch=1,
    )
    assert store.reserve(malformed) == "identity_or_scope_denied"
    assert store.reserved_for_test("church", GEO) == 0
    bad = tmp_path / "corrupt.sqlite3"
    bad.write_bytes(b"PRIVATE_CORRUPT_DATABASE")
    assert DurableCentralReservationE0(bad).reserve(
        _request("private")
    ) == "synthetic_authority_unavailable"
    with pytest.raises(RuntimeError, match="revocation unavailable"):
        DurableCentralReservationE0(bad).revoke_all()
    assert bad.read_bytes() == b"PRIVATE_CORRUPT_DATABASE"


def test_independent_spawned_processes_observe_one_atomic_tenant_quota(tmp_path):
    path = tmp_path / "shared-host.sqlite3"
    store = _fixture(path, cap=2)
    with ProcessPoolExecutor(
        max_workers=4, mp_context=get_context("spawn"),
    ) as pool:
        futures = [
            pool.submit(_independent_reserve, str(path), str(i), "church")
            for i in range(10)
        ]
        decisions = [f.result(timeout=30) for f in futures]
    assert decisions.count("synthetic_reservation") == 2
    assert decisions.count("allowance_exhausted") == 8
    assert store.reserved_for_test("church", GEO) == 2


def test_distinct_os_process_stop_blocks_all_new_reservations(tmp_path):
    path = tmp_path / "cross-process-revoke.sqlite3"
    store = _fixture(path, cap=2)
    assert store.reserve(_request("before")) == "synthetic_reservation"
    with ProcessPoolExecutor(
        max_workers=1, mp_context=get_context("spawn"),
    ) as pool:
        assert pool.submit(
            _independent_revoke, str(path), "church",
        ).result(timeout=30) is True
    for i in range(12):
        assert store.reserve(_request(f"after-{i}")) == "operator_revoked"
    assert store.reserved_for_test("church", GEO) == 1
    assert store.reserve(
        _request("unaffected-tenant", tenant="school")
    ) == "synthetic_reservation"


def test_local_racing_stop_never_reopens_lease_or_exceeds_quota(tmp_path):
    path = tmp_path / "race.sqlite3"
    store = _fixture(path, cap=2)
    with ThreadPoolExecutor(max_workers=9) as pool:
        futures = [
            pool.submit(store.reserve, _request(f"candidate-{i}"))
            for i in range(8)
        ]
        stop = pool.submit(store.revoke_tenant, "church")
        decisions = [f.result(timeout=10) for f in futures]
        assert stop.result(timeout=10) is True
    assert decisions.count("synthetic_reservation") <= 2
    assert store.reserved_for_test("church", GEO) <= 2
    assert store.reserve(_request("new")) == "operator_revoked"


def test_empty_or_partial_schema_is_not_implicitly_repaired(tmp_path):
    path = tmp_path / "partial.sqlite3"
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE unrelated (id INTEGER)")
    store = DurableCentralReservationE0(path)
    assert store.reserve(_request("new")) == "synthetic_authority_unavailable"
    with pytest.raises(FileExistsError):
        store.provision_once(
            allowed={("church", "worker-a", GEO): "geo-revision-1"},
            cap_per_tenant_route=1,
        )
