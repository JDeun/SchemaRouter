from __future__ import annotations

import pytest

from examples.external_validation.safeact_v1.evidence_gate import (
    ActionContract,
    EvidenceGate,
    Observation,
)


def _gate() -> EvidenceGate:
    return EvidenceGate(ActionContract(
        action="refund_issue",
        required_observations=(("charge_read", "C2", frozenset({"amount", "owner"})),),
    ))


def test_missing_observation_blocks_without_invoking_executor() -> None:
    gate = _gate()
    calls = []
    try:
        gate.dispatch("refund_issue", {"charge_id": "C2"}, lambda *args: calls.append(args))
    except PermissionError:
        pass
    else:
        raise AssertionError("missing evidence was not blocked")
    assert not calls


def test_wrong_entity_cannot_satisfy_contract() -> None:
    gate = _gate()
    gate.observe(Observation("charge_read", "C1", frozenset({"amount", "owner"})))
    assert not gate.check("refund_issue").allowed


def test_partial_fields_cannot_satisfy_contract() -> None:
    gate = _gate()
    gate.observe(Observation("charge_read", "C2", frozenset({"amount"})))
    assert not gate.check("refund_issue").allowed


def test_successful_observation_enables_dispatch() -> None:
    gate = _gate()
    gate.observe(Observation("charge_read", "C2", frozenset({"amount", "owner"})))
    assert gate.dispatch("refund_issue", {"charge_id": "C2"}, lambda name, args: (name, args)) == (
        "refund_issue", {"charge_id": "C2"}
    )


def test_failed_observation_does_not_count() -> None:
    gate = _gate()
    gate.observe(Observation("charge_read", "C2", frozenset({"amount", "owner"}), successful=False))
    assert not gate.check("refund_issue").allowed


def test_wrong_action_blocks() -> None:
    gate = _gate()
    gate.observe(Observation("charge_read", "C2", frozenset({"amount", "owner"})))
    assert gate.check("delete_charge").missing == ("action_mismatch",)

def test_evidence_for_one_record_cannot_authorize_another_target() -> None:
    gate = EvidenceGate(
        ActionContract(
            action="refund_issue",
            required_observations=(("charge_read", "C2", frozenset({"owner"})),),
            argument_bindings=(("charge_id", "C2"),),
        )
    )
    gate.observe(Observation("charge_read", "C2", frozenset({"owner"})))
    calls: list[object] = []
    with pytest.raises(PermissionError, match="argument_binding_mismatch"):
        gate.dispatch("refund_issue", {"charge_id": "C1"}, lambda *args: calls.append(args))
    assert calls == []
    assert not gate.check("refund_issue").allowed
    assert not gate.check("refund_issue", {}).allowed
    assert gate.check("refund_issue", {"charge_id": "C2"}).allowed


def test_action_binding_must_name_a_declared_observation() -> None:
    with pytest.raises(ValueError, match="argument binding"):
        EvidenceGate(
            ActionContract(
                action="refund_issue",
                required_observations=(("charge_read", "C2", frozenset({"owner"})),),
                argument_bindings=(("charge_id", "C1"),),
            )
        )


def test_dynamic_action_bound_record_only_accepts_observed_target() -> None:
    gate = EvidenceGate(
        ActionContract(
            action="refund_issue",
            required_observations=(
                ("charge_read", "$action.charge_id", frozenset({"owner"})),
            ),
        )
    )
    gate.observe(Observation("charge_read", "C2", frozenset({"owner"})))
    assert gate.check("refund_issue", {"charge_id": "C2"}).allowed
    assert not gate.check("refund_issue", {"charge_id": "C1"}).allowed
    assert not gate.check("refund_issue", {}).allowed
    assert not gate.check("refund_issue", {"charge_id": 42}).allowed


@pytest.mark.parametrize("reference", ["$action.", "$action.a-b", "$action.a.b"])
def test_invalid_dynamic_argument_name_fails_closed(reference: str) -> None:
    with pytest.raises(ValueError, match="malformed action-bound"):
        EvidenceGate(
            ActionContract(
                action="refund_issue",
                required_observations=(
                    ("charge_read", reference, frozenset({"owner"})),
                ),
            )
        )
