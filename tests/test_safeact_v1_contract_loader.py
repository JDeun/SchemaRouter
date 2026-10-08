from __future__ import annotations

import pytest

from examples.external_validation.safeact_v1.contract_loader import build_gate
from examples.external_validation.safeact_v1.evidence_gate import Observation


def _document(path: str = "contracts/safeact-v1/refund.json") -> dict:
    return {"contracts": [{
        "action": "refund_issue",
        "sources": [{"kind": "independent_contract", "path": path}],
        "required_observations": [
            {"tool": "charge_read", "record_id": "C2", "fields": ["amount", "owner"]}
        ],
    }]}


def test_valid_independent_contract_loads() -> None:
    gate = build_gate(_document(), "refund_issue")
    assert not gate.check("refund_issue").allowed
    gate.observe(Observation("charge_read", "C2", frozenset({"amount", "owner"})))
    assert gate.check("refund_issue").allowed


@pytest.mark.parametrize("path", [
    "env/case_evidence.json",
    "env/case_manifest.json",
    "env/case_provenance.json",
    "data/safeact/cases.json",
])
def test_evaluator_sources_cannot_construct_gate(path: str) -> None:
    with pytest.raises(ValueError, match="untrusted contract"):
        build_gate(_document(path), "refund_issue")


def test_missing_provenance_rejected() -> None:
    document = _document()
    document["contracts"][0]["sources"] = []
    with pytest.raises(ValueError, match="untrusted contract"):
        build_gate(document, "refund_issue")


def test_ambiguous_contract_rejected() -> None:
    document = _document()
    document["contracts"].append(document["contracts"][0].copy())
    with pytest.raises(ValueError, match="exactly once"):
        build_gate(document, "refund_issue")


def test_missing_fields_rejected() -> None:
    document = _document()
    document["contracts"][0]["required_observations"][0]["fields"] = []
    with pytest.raises(ValueError, match="typed fields"):
        build_gate(document, "refund_issue")

def test_loader_binds_action_target_to_observed_record() -> None:
    document = _document()
    document["contracts"][0]["argument_bindings"] = [
        {"argument": "charge_id", "record_id": "C2"}
    ]
    gate = build_gate(document, "refund_issue")
    gate.observe(Observation("charge_read", "C2", frozenset({"amount", "owner"})))
    assert gate.check("refund_issue", {"charge_id": "C2"}).allowed
    assert not gate.check("refund_issue", {"charge_id": "C1"}).allowed


def test_loader_rejects_nonexistent_action_target() -> None:
    document = _document()
    document["contracts"][0]["argument_bindings"] = [
        {"argument": "charge_id", "record_id": "C1"}
    ]
    with pytest.raises(ValueError, match="argument binding"):
        build_gate(document, "refund_issue")


def test_loader_rejects_duplicate_argument_bindings() -> None:
    document = _document()
    document["contracts"][0]["argument_bindings"] = [
        {"argument": "charge_id", "record_id": "C2"},
        {"argument": "charge_id", "record_id": "C2"},
    ]
    with pytest.raises(ValueError, match="duplicate argument binding"):
        build_gate(document, "refund_issue")


def test_loader_allows_independent_action_record_templates() -> None:
    document = _document()
    document["contracts"][0]["required_observations"][0]["record_id"] = (
        "$action.charge_id"
    )
    gate = build_gate(document, "refund_issue")
    gate.observe(Observation("charge_read", "C2", frozenset({"amount", "owner"})))
    assert gate.check("refund_issue", {"charge_id": "C2"}).allowed
    assert not gate.check("refund_issue", {"charge_id": "C1"}).allowed
