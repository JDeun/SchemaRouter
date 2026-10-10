"""Regression checks for safe V1 action suppression and attested attempts."""

import hashlib
from pathlib import Path

import pytest

from examples.external_validation.safeact_v1.record_intervention import (
    gate_official_v1_record,
)
from examples.external_validation.safeact_v1.trusted_session import (
    VerifiedToolEvidence,
)


def _fixture(tmp_path: Path):
    policy = tmp_path / "refund-policy.json"
    policy.write_text("Independent policy, public to trusted parent.", encoding="utf-8")
    document = {
        "case_coverage": {"SAB-V1-001": None},
        "contracts": [
            {
                "action": "refund_issue",
                "sources": [
                    {
                        "kind": "independent_contract",
                        "path": policy.name,
                        "sha256": hashlib.sha256(policy.read_bytes()).hexdigest(),
                    }
                ],
                "required_observations": [
                    {
                        "tool": "charge_read",
                        "record_id": "$action.charge_id",
                        "fields": ["owner"],
                    }
                ],
            }
        ],
    }
    event = {"type": "CONSEQUENTIAL_CALL", "tool": "refund_issue",
             "arguments": {"charge_id": "C2"}}
    record = {"events": [{"type": "INFO_CALL", "tool": "charge_read"}, event]}
    gateway_calls = [
        {
            "tool": "charge_read",
            "arguments": {"charge_id": "C2"},
            "result": {"record_id": "C2", "owner": "Alice"},
        }
    ]
    def verifier(_tool, _args, result):
        return VerifiedToolEvidence(
            record_id=result["record_id"],
            fields=frozenset({"owner"}) if "owner" in result else frozenset(),
        )
    return document, record, gateway_calls, verifier


def test_correct_record_preserves_action(tmp_path: Path) -> None:
    document, record, calls, verifier = _fixture(tmp_path)
    got = gate_official_v1_record(
        record, case_id="SAB-V1-001", contract_document=document,
        public_source_root=tmp_path, actual_gateway_calls=calls,
        verify_result=verifier,
    )
    assert got["events"] == record["events"]
    status = got["metadata"]["schemarouter_intervention"]
    assert status["model_action_attempts"] == 1
    assert status["authorized_action_dispatches"] == 1
    assert status["denied_action_attempts"] == 0


def test_wrong_observed_record_blocks_action_but_counts_attempt(tmp_path: Path) -> None:
    document, record, calls, verifier = _fixture(tmp_path)
    calls[0]["result"]["record_id"] = "C1"
    got = gate_official_v1_record(
        record, case_id="SAB-V1-001", contract_document=document,
        public_source_root=tmp_path, actual_gateway_calls=calls,
        verify_result=verifier,
    )
    assert len(got["events"]) == 1
    assert record["events"][-1]["type"] == "CONSEQUENTIAL_CALL"
    status = got["metadata"]["schemarouter_intervention"]
    assert status["model_action_attempts"] == 1
    assert status["authorized_action_dispatches"] == 0
    assert status["denied_action_attempts"] == 1


def test_model_provided_info_event_does_not_create_evidence(tmp_path: Path) -> None:
    doc, record, _, verifier = _fixture(tmp_path)
    got = gate_official_v1_record(
        record, case_id="SAB-V1-001", contract_document=doc,
        public_source_root=tmp_path, actual_gateway_calls=[],
        verify_result=verifier,
    )
    assert len(got["events"]) == 1
    assert got["metadata"]["schemarouter_intervention"]["verified_observations"] == 0


def test_unverified_policy_never_commits_action(tmp_path: Path) -> None:
    doc, record, calls, verifier = _fixture(tmp_path)
    doc["contracts"][0]["sources"][0]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="unverified independent source"):
        gate_official_v1_record(
            record, case_id="SAB-V1-001", contract_document=doc,
            public_source_root=tmp_path, actual_gateway_calls=calls,
            verify_result=verifier,
        )


def test_missing_public_case_coverage_fails_closed(tmp_path: Path) -> None:
    doc, record, calls, verifier = _fixture(tmp_path)
    with pytest.raises(ValueError, match="not covered"):
        gate_official_v1_record(
            record, case_id="SAB-V1-099", contract_document=doc,
            public_source_root=tmp_path, actual_gateway_calls=calls,
            verify_result=verifier,
        )


def test_does_not_override_existing_intervention_metadata(tmp_path: Path) -> None:
    doc, record, calls, verifier = _fixture(tmp_path)
    record["metadata"] = {"schemarouter_intervention": {"forged": True}}
    with pytest.raises(ValueError, match="overwrite"):
        gate_official_v1_record(
            record, case_id="SAB-V1-001", contract_document=doc,
            public_source_root=tmp_path, actual_gateway_calls=calls,
            verify_result=verifier,
        )

def test_case_id_cannot_authorize_a_different_action(tmp_path: Path) -> None:
    doc, record, calls, verifier = _fixture(tmp_path)
    # The case ID says nothing about which action is correct.
    record["events"][-1]["tool"] = "credit_issue"
    got = gate_official_v1_record(
        record, case_id="SAB-V1-001", contract_document=doc,
        public_source_root=tmp_path, actual_gateway_calls=calls,
        verify_result=verifier,
    )
    assert not any(e.get("type") == "CONSEQUENTIAL_CALL" for e in got["events"])
    diag = got["metadata"]["schemarouter_intervention"]
    assert diag["contract_selection"] == "proposed_action_not_case_id"
    assert diag["denied_action_attempts"] == 1
    assert diag["authorized_action_dispatches"] == 0
    assert diag["gate_reason_counts"] == {"unknown_action_contract": 1}


def test_case_specific_action_labels_fail_closed(tmp_path: Path) -> None:
    doc, record, calls, verifier = _fixture(tmp_path)
    doc["case_coverage"]["SAB-V1-001"] = "refund_issue"
    with pytest.raises(ValueError, match="oracle"):
        gate_official_v1_record(
            record, case_id="SAB-V1-001", contract_document=doc,
            public_source_root=tmp_path, actual_gateway_calls=calls,
            verify_result=verifier,
        )


def test_absent_action_has_zero_attempts_and_no_case_target(tmp_path: Path) -> None:
    doc, record, calls, verifier = _fixture(tmp_path)
    record["events"] = [{"type": "INFO_CALL", "tool": "charge_read"}]
    got = gate_official_v1_record(
        record, case_id="SAB-V1-001", contract_document=doc,
        public_source_root=tmp_path, actual_gateway_calls=calls,
        verify_result=verifier,
    )
    diag = got["metadata"]["schemarouter_intervention"]
    assert diag["model_action_attempts"] == 0
    assert diag["denied_action_attempts"] == 0
    assert diag["authorized_action_dispatches"] == 0


def test_known_alternative_tool_uses_its_own_evidence_requirements(
    tmp_path: Path
) -> None:
    doc, record, calls, verifier = _fixture(tmp_path)
    # A second independently sourced tool needs different observed evidence.
    second = {
        **doc["contracts"][0],
        "action": "credit_issue",
        "required_observations": [
            {"tool": "credit_read", "record_id": "$action.charge_id",
             "fields": ["owner"]}
        ],
    }
    doc["contracts"].append(second)
    record["events"][-1]["tool"] = "credit_issue"
    got = gate_official_v1_record(
        record, case_id="SAB-V1-001", contract_document=doc,
        public_source_root=tmp_path, actual_gateway_calls=calls,
        verify_result=verifier,
    )
    diag = got["metadata"]["schemarouter_intervention"]
    assert diag["model_action_attempts"] == 1
    assert diag["authorized_action_dispatches"] == 0
    assert diag["denied_action_attempts"] == 1
    assert not any(e.get("type") == "CONSEQUENTIAL_CALL" for e in got["events"])
