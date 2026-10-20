"""Synthetic E0 serialized egress gate tests; no network, IAM or provider."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest

from scripts.research_central_egress_admission_e0 import (
    CentralEgressLinearizationModelE0,
    SyntheticEgressRequestE0,
)
from scripts.research_live_health_model_menu_e1 import GEO, WEATHER


def _authority(*, cap: int = 2) -> CentralEgressLinearizationModelE0:
    return CentralEgressLinearizationModelE0(
        provisioned={
            ("church", "agent-a", GEO): "source-sha-geocode",
            ("church", "agent-b", GEO): "source-sha-geocode",
            ("church", "agent-a", WEATHER): "source-sha-forecast",
        },
        attempts_per_route=cap,
    )


def _request(
    identifier: str, *, worker: str = "agent-a", route: str = GEO,
    fingerprint: str = "source-sha-geocode", epoch: int = 1,
    tenant: str = "church",
) -> SyntheticEgressRequestE0:
    return SyntheticEgressRequestE0(
        tenant=tenant, workload=worker, route_id=route,
        source_fingerprint=fingerprint, request_id=identifier, epoch=epoch,
    )


def test_two_independent_workers_race_for_nonrefundable_atomic_allowance():
    gate = _authority()
    forwarded: list[str] = []

    def attempt(i: int) -> str:
        actor = "agent-a" if i % 2 else "agent-b"
        return gate.admit_and_handoff(
            _request(str(i), worker=actor),
            synthetic_handoff=lambda: forwarded.append(str(i)),
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        decisions = list(pool.map(attempt, range(20)))
    assert decisions.count("synthetic_handoff") == 2
    assert decisions.count("allowance_exhausted") == 18
    assert gate.forwarded_synthetic_attempts == 2
    assert gate.spent_by_route() == {"geocoding": 2, "forecast": 0}
    assert len(forwarded) == 2


def test_revocation_invalidates_epoch_and_never_resurrects_allowance():
    gate = _authority(cap=1)
    forwarded: list[bool] = []
    assert gate.admit_and_handoff(
        _request("original"),
        synthetic_handoff=lambda: forwarded.append(True),
    ) == "synthetic_handoff"
    assert gate.revoke() is True
    assert gate.revoke() is False
    assert gate.epoch == 2
    for epoch in (1, 2):
        assert gate.admit_and_handoff(
            _request(f"later-{epoch}", epoch=epoch),
            synthetic_handoff=lambda: forwarded.append(True),
        ) == "operator_revoked"
    assert forwarded == [True]
    assert gate.spent_by_route() == {"geocoding": 1, "forecast": 0}


@pytest.mark.parametrize(
    ("candidate", "expected"),
    (
        (_request("wrong-worker", worker="other"), "identity_or_scope_denied"),
        (_request("wrong-tenant", tenant="other"), "identity_or_scope_denied"),
        (_request("wrong-source", fingerprint="mismatched"), "identity_or_scope_denied"),
        (
            _request("wrong-operation", route="open_meteo_weather.delete"),
            "identity_or_scope_denied",
        ),
        (_request("wrong-epoch", epoch=0), "stale_epoch"),
    ),
)
def test_pinned_identity_source_route_and_epoch_are_all_required(candidate, expected):
    gate = _authority()
    assert gate.admit_and_handoff(
        candidate, synthetic_handoff=lambda: pytest.fail("untrusted forwarded"),
    ) == expected
    assert gate.forwarded_synthetic_attempts == 0


def test_idempotency_prevents_duplicate_dispatch_even_across_worker_identity():
    gate = _authority()
    emitted: list[str] = []
    assert gate.admit_and_handoff(
        _request("same"),
        synthetic_handoff=lambda: emitted.append("first"),
    ) == "synthetic_handoff"
    assert gate.admit_and_handoff(
        _request("same", worker="agent-b"),
        synthetic_handoff=lambda: emitted.append("duplicate"),
    ) == "duplicate_request"
    assert emitted == ["first"]
    assert gate.spent_by_route()["geocoding"] == 1


def test_synthetic_sink_error_does_not_refund_or_expose_private_exception():
    gate = _authority(cap=1)

    def failing() -> None:
        raise RuntimeError("PRIVATE_PROVIDER_RESPONSE")

    assert gate.admit_and_handoff(
        _request("first"), synthetic_handoff=failing,
    ) == "synthetic_handoff_failed"
    assert gate.admit_and_handoff(
        _request("second"), synthetic_handoff=lambda: None,
    ) == "allowance_exhausted"
    assert gate.spent_by_route() == {"geocoding": 1, "forecast": 0}


def test_revoke_is_serialized_with_synthetic_handoff_not_prior_client_check():
    gate = _authority()
    handoff_started = Event()
    allow_finish = Event()
    emitted: list[str] = []

    def synthetic_handoff() -> None:
        handoff_started.set()
        if not allow_finish.wait(timeout=10):
            raise RuntimeError("synthetic test timeout")
        emitted.append("before-revocation")

    with ThreadPoolExecutor(max_workers=2) as pool:
        dispatched = pool.submit(
            gate.admit_and_handoff, _request("before"),
            synthetic_handoff=synthetic_handoff,
        )
        assert handoff_started.wait(timeout=10)
        stopping = pool.submit(gate.revoke)
        allow_finish.set()
        assert dispatched.result(timeout=10) == "synthetic_handoff"
        assert stopping.result(timeout=10) is True
    assert emitted == ["before-revocation"]
    assert gate.admit_and_handoff(
        _request("after", epoch=2),
        synthetic_handoff=lambda: emitted.append("after-revocation"),
    ) == "operator_revoked"
    assert emitted == ["before-revocation"]


def test_no_automatic_restart_or_untrusted_synthetic_gateway_initialization():
    with pytest.raises(ValueError, match="provisioned"):
        CentralEgressLinearizationModelE0(
            provisioned={}, attempts_per_route=1,
        )
    old = _authority(cap=1)
    assert old.revoke() is True
    # In this E0 simulation a new object is NOT a persistence or restart
    # proof. No production state/authority exists to auto-resume.
    assert old.admit_and_handoff(
        _request("denied"), synthetic_handoff=lambda: None,
    ) == "operator_revoked"
