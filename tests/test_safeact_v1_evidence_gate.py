from __future__ import annotations

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
