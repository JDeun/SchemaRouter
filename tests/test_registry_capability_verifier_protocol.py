from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "benchmarks" / "operation-routing-v4-registry-capability-verifier.json"
VERIFIER = ROOT / "benchmarks" / "registry_capability_verifier.py"


def test_manifest_freezes_arbitrary_registration_generalization() -> None:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    generalization = data["registry_generalization"]

    assert data["work_item"] == 338
    assert generalization["native_tools_required"] is True
    assert generalization["openapi_import_required"] is True
    assert generalization["mcp_import_required"] is True
    assert generalization["operation_aliases_may_be_empty"] is True
    assert generalization["variable_endpoint_counts_required"] == [1, 3, 5]
    assert generalization["route_ids_forbidden_as_learned_features"] is True
    assert generalization["benchmark_domain_keyword_rules_forbidden"] is True
    assert generalization["route_local_thresholds_forbidden"] is True
    assert generalization["new_tool_requires_route_specific_retraining"] is False


def test_manifest_keeps_verifier_veto_only_and_fresh_surfaces_forbidden() -> None:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    authority = data["route_authority"]
    dev = data["canonical_dev"]

    assert authority["raw_registered_top1_only"] is True
    assert authority["verifier_veto_only"] is True
    assert authority["verifier_can_change_route"] is False
    assert authority["rank2_fallback"] is False
    assert authority["pseudo_route"] is False
    assert dev["forbidden_fresh_issues"] == [270, 287, 326]
    assert dev["calibration_or_blind_forbidden"] is True


def test_verifier_source_contains_no_canonical_route_identity_rules() -> None:
    source = VERIFIER.read_text(encoding="utf-8")
    for forbidden in (
        "weather.current",
        "materials.search",
        "papers.citations",
        "finance.quote",
        "calendar.create",
        "support.search",
        "inventory.update",
        "users.lookup",
    ):
        assert forbidden not in source


def test_stopping_rule_requires_both_surfaces_before_fresh() -> None:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    stopping = data["stopping_rule"]

    assert stopping["if_canonical_or_registration_holdout_fails"] == (
        "terminal_reject_without_label_driven_repair"
    )
    assert "brand-new zero-overlap fresh confirmation" in stopping["if_both_pass"]
    assert stopping["issue_198"] == "remains_blocked_until_new_fresh_confirmation_passes"



def test_manifest_freezes_typed_data_contract_ir() -> None:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    contract = data["data_contract_ir"]

    assert contract["preserve_semantic_id"] is True
    assert contract["preserve_json_schema_type_shape"] is True
    assert contract["preserve_source_unit"] is True
    assert contract["preserve_unit_normalization"] == [
        "dimension",
        "canonical_unit",
        "scale",
        "offset",
    ]
    assert contract["preserve_qualifiers"] is True
    assert contract["openapi_and_mcp_same_ir"] is True
    assert contract["enforcement_role"] == (
        "deterministic_registered_metadata_not_model_authority"
    )
