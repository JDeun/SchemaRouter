"""SafeAct V1 trusted evidence-session mechanism regression tests."""
from __future__ import annotations

import pytest

from examples.external_validation.safeact_v1.trusted_session import (
    TrustedEvidenceSession,
    VerifiedToolEvidence,
)


def _contract() -> dict[str, object]:
    return {
        "contracts": [{
            "action": "refund_issue",
            "sources": [{
                "kind": "independent_contract",
                "path": "contracts/refunds/public-policy.json",
            }],
            "required_observations": [{
                "tool": "charge_read",
                "record_id": "C2",
                "fields": ["amount", "owner"],
            }],
        }],
    }


def _session(*, read=None, verify=None, execute=None) -> TrustedEvidenceSession:
    return TrustedEvidenceSession(
        _contract(),
        "refund_issue",
        information_call=read or (
            lambda tool, args: {"charge_id": "C2", "amount": 15, "owner": "Alice"}
        ),
        verify_result=verify or (
            lambda tool, args, result: VerifiedToolEvidence(
                record_id=result["charge_id"],
                fields=frozenset(field for field in ("amount", "owner") if field in result),
            )
        ),
        execute_action=execute or (lambda action, args: (action, args)),
    )


def test_no_prior_observation_never_executes_action() -> None:
    actions = []
    session = _session(execute=lambda action, args: actions.append(action))
    with pytest.raises(PermissionError, match="evidence incomplete"):
        session.execute_action("refund_issue", {"charge_id": "C2"})
    assert actions == []


def test_real_verified_read_unblocks_only_matching_action() -> None:
    calls = []
    observed = {"charge_id": "C2", "amount": 15, "owner": "Alice"}
    session = _session(read=lambda tool, args: calls.append(tool) or observed)
    assert session.information_call("charge_read", {}) == observed
    assert calls == ["charge_read"]
    assert session.execute_action("refund_issue", {"charge_id": "C2"}) == (
        "refund_issue", {"charge_id": "C2"},
    )
    with pytest.raises(PermissionError, match="action_mismatch"):
        session.execute_action("delete_charge", {})


def test_result_entity_mismatch_cannot_be_forged_by_arguments() -> None:
    session = _session(read=lambda tool, args: {"charge_id": "C1", "amount": 15})
    session.information_call("charge_read", {"charge_id": "C2"})
    with pytest.raises(PermissionError, match="evidence incomplete"):
        session.execute_action("refund_issue", {})


def test_partial_or_unverified_read_does_not_unlock_action() -> None:
    session = _session(
        verify=lambda tool, args, result: VerifiedToolEvidence(
            "C2", frozenset({"amount"}),
        ),
    )
    session.information_call("charge_read", {})
    with pytest.raises(PermissionError):
        session.execute_action("refund_issue", {})

    unverified = _session(verify=lambda tool, args, result: None)
    unverified.information_call("charge_read", {})
    with pytest.raises(PermissionError):
        unverified.execute_action("refund_issue", {})


def test_failed_information_call_cannot_create_evidence() -> None:
    def unavailable(tool, args):
        raise RuntimeError("tool failed")

    session = _session(read=unavailable)
    with pytest.raises(RuntimeError, match="tool failed"):
        session.information_call("charge_read", {})
    with pytest.raises(PermissionError):
        session.execute_action("refund_issue", {})


def test_sessions_do_not_share_observations() -> None:
    first = _session()
    second = _session()
    first.information_call("charge_read", {})
    assert first.execute_action("refund_issue", {}) == ("refund_issue", {})
    with pytest.raises(PermissionError):
        second.execute_action("refund_issue", {})


def test_malformed_verifier_evidence_is_rejected() -> None:
    session = _session(
        verify=lambda tool, args, result: VerifiedToolEvidence("C2", frozenset()),
    )
    with pytest.raises(ValueError, match="malformed observed evidence"):
        session.information_call("charge_read", {})


def test_evaluator_only_contract_rejected_before_execution() -> None:
    document = _contract()
    document["contracts"][0]["sources"][0]["path"] = "safeact/env/case_manifest.json"
    with pytest.raises(ValueError, match="untrusted contract"):
        TrustedEvidenceSession(
            document,
            "refund_issue",
            information_call=lambda tool, args: {},
            verify_result=lambda tool, args, result: None,
            execute_action=lambda action, args: None,
        )


def test_mechanism_diagnostics_track_attempts_and_denials() -> None:
    session = _session()
    with pytest.raises(PermissionError):
        session.execute_action("refund_issue", {})
    session.information_call("charge_read", {})
    assert session.execute_action("refund_issue", {}) == ("refund_issue", {})
    assert session.diagnostics() == {
        "information_attempts": 1,
        "verified_observations": 1,
        "action_attempts": 2,
        "action_dispatches": 1,
        "gate_denials": 1,
        "gate_reason_counts": {"missing_required_observation": 1},
    }


def test_failed_read_counts_attempt_without_crediting_evidence() -> None:
    def fail(tool, args):
        raise RuntimeError("transport failed")

    session = _session(read=fail)
    with pytest.raises(RuntimeError):
        session.information_call("charge_read", {})
    assert session.diagnostics()["information_attempts"] == 1
    assert session.diagnostics()["verified_observations"] == 0


def test_mismatched_action_reason_is_coarsened() -> None:
    session = _session()
    with pytest.raises(PermissionError):
        session.execute_action("delete_charge", {"charge_id": "C2"})
    assert session.diagnostics()["gate_reason_counts"] == {"action_mismatch": 1}



def test_bound_action_target_checks_runtime_arguments() -> None:
    contract = _contract()
    contract["contracts"][0]["argument_bindings"] = [
        {"argument": "charge_id", "record_id": "C2"}
    ]
    dispatched: list[tuple[str, dict]] = []
    session = TrustedEvidenceSession(
        contract,
        "refund_issue",
        information_call=lambda tool, args: {
            "charge_id": "C2", "amount": 15, "owner": "Alice"
        },
        verify_result=lambda tool, args, result: VerifiedToolEvidence(
            record_id=result["charge_id"],
            fields=frozenset({"amount", "owner"}),
        ),
        execute_action=lambda action, args: dispatched.append((action, args)),
    )
    session.information_call("charge_read", {"charge_id": "C2"})
    with pytest.raises(PermissionError, match="argument_binding_mismatch"):
        session.execute_action("refund_issue", {"charge_id": "C1"})
    assert dispatched == []
    assert session.diagnostics()["gate_reason_counts"] == {
        "argument_binding_mismatch": 1
    }
    assert session.diagnostics()["action_dispatches"] == 0
    session.execute_action("refund_issue", {"charge_id": "C2"})
    assert dispatched == [("refund_issue", {"charge_id": "C2"})]
    assert session.diagnostics()["action_dispatches"] == 1


def test_missing_bound_argument_never_dispatches() -> None:
    contract = _contract()
    contract["contracts"][0]["argument_bindings"] = [
        {"argument": "charge_id", "record_id": "C2"}
    ]
    dispatched: list[str] = []
    session = TrustedEvidenceSession(
        contract,
        "refund_issue",
        information_call=lambda tool, args: {"charge_id": "C2", "owner": "Alice"},
        verify_result=lambda tool, args, result: VerifiedToolEvidence(
            record_id="C2", fields=frozenset({"amount", "owner"})
        ),
        execute_action=lambda action, args: dispatched.append(action),
    )
    session.information_call("charge_read", {"charge_id": "C2"})
    with pytest.raises(PermissionError, match="argument_binding_mismatch"):
        session.execute_action("refund_issue", {})
    assert dispatched == []
