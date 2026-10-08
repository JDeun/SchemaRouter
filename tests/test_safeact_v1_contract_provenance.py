from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "validate_safeact_v1_contract_provenance.py"
)
SPEC = importlib.util.spec_from_file_location("safeact_contract_provenance", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _contract(path: str, kind: str = "public_policy") -> dict[str, object]:
    return {
        "contracts": [
            {
                "action": "refund_issue",
                "sources": [{"kind": kind, "path": path}],
                "required": {"provenance": True},
            }
        ]
    }


def test_public_policy_source_is_allowed() -> None:
    document = _contract("env/customer_policy_qa/world/policies/workflow_policies.json")
    assert MODULE.validate(document) == []


def test_case_evidence_is_forbidden() -> None:
    errors = MODULE.validate(_contract("env/case_evidence.json"))
    assert any("forbidden evaluator source path" in error for error in errors)


def test_materialized_gold_evidence_is_forbidden() -> None:
    errors = MODULE.validate(
        _contract("env/customer_policy_qa/materialized_evidence/SAB-V1-009.json")
    )
    assert any("materialized_evidence" in error for error in errors)


def test_evaluator_fields_cannot_be_embedded() -> None:
    document = _contract("contracts/safeact-v1/refund.json", "independent_contract")
    document["contracts"][0]["expected_outcome"] = "TASK_SUCCESS"  # type: ignore[index]
    errors = MODULE.validate(document)
    assert any("expected_outcome" in error for error in errors)


def test_unknown_source_kind_fails_closed() -> None:
    errors = MODULE.validate(_contract("somewhere.json", "benchmark_gold"))
    assert any("forbidden source kind" in error for error in errors)


def test_nested_evaluator_paths_are_forbidden_even_under_trusted_prefix() -> None:
    # A checkout prefix must not turn benchmark evaluator inputs into trusted policy.
    for path in (
        "safeact/env/case_manifest.json",
        "checkout/data/safeact/cases.json",
        "trusted/env/case_provenance.json",
        "root/env/case_evidence.json",
        "SAFEACT/ENV/CASE_MANIFEST.JSON",
    ):
        errors = MODULE.validate(_contract(path))
        assert any("forbidden evaluator source path" in error for error in errors), path


def test_public_policy_under_workspace_prefix_remains_allowed() -> None:
    document = _contract("workspace/env/customer_policy_qa/world/policies/refunds.md")
    assert MODULE.validate(document) == []
