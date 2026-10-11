"""Synthetic post-run treatment-integrity regressions; not model scores."""

import json
from pathlib import Path

import pytest

from scripts.verify_safeact_v1_interventions import (
    EXPECTED_KINDS,
    verify_arm_interventions,
)


def _outputs(tmp_path: Path) -> dict[str, Path]:
    outputs: dict[str, Path] = {}
    for condition, kind in EXPECTED_KINDS.items():
        folder = tmp_path / condition / "normalized_results" / "v1"
        folder.mkdir(parents=True)
        case = "SAB-V1-001"
        metadata = {}
        if kind is not None:
            metadata["schemarouter_intervention"] = {
                "kind": kind,
                "case_id": case,
                "evaluator_data_used": False,
                "action_effect_boundary": "normalized_record_only",
                "physical_action_execution_observed": False,
                "model_action_attempts": 1,
                "authorized_action_dispatches": 1,
                "denied_action_attempts": 0,
            }
        (folder / f"{case}.json").write_text(
            json.dumps({
                "events": [{"type": "CONSEQUENTIAL_CALL", "tool": "synthetic"}],
                "metadata": metadata,
            }), encoding="utf-8"
        )
        outputs[condition] = tmp_path / condition
    return outputs


def test_all_three_attested_conditions_are_accepted(tmp_path: Path) -> None:
    result = verify_arm_interventions(_outputs(tmp_path), expected_cases=1)
    assert len(result) == 3
    assert result["SAFEACT-UNGATED"]["model_action_attempts"] is None


def test_routing_only_cannot_fake_gated_or_baseline_arm(tmp_path: Path) -> None:
    outputs = _outputs(tmp_path)
    condition = "SAFEACT-SCHEMAROUTER-NO-EVIDENCE-GATE"
    path = outputs[condition] / "normalized_results/v1/SAB-V1-001.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["metadata"]["schemarouter_intervention"]["kind"] = (
        "trusted_official_v1_record_gate"
    )
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="missing trusted intervention"):
        verify_arm_interventions(outputs, expected_cases=1)


def test_false_dispatch_or_denial_counts_are_rejected(tmp_path: Path) -> None:
    outputs = _outputs(tmp_path)
    condition = "SAFEACT-SCHEMAROUTER-EVIDENCE-GATE"
    path = outputs[condition] / "normalized_results/v1/SAB-V1-001.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["metadata"]["schemarouter_intervention"]["denied_action_attempts"] = 1
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="accounting drift"):
        verify_arm_interventions(outputs, expected_cases=1)


def test_missing_routing_only_proof_never_reports_results(tmp_path: Path) -> None:
    outputs = _outputs(tmp_path)
    condition = "SAFEACT-SCHEMAROUTER-NO-EVIDENCE-GATE"
    path = outputs[condition] / "normalized_results/v1/SAB-V1-001.json"
    value = {"metadata": {}}
    path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(ValueError, match="missing trusted intervention"):
        verify_arm_interventions(outputs, expected_cases=1)


@pytest.mark.parametrize("change", [
    {"action_effect_boundary": None},
    {"action_effect_boundary": "actual_tool_execution"},
    {"physical_action_execution_observed": True},
    {"physical_action_execution_observed": None},
])
def test_unverified_physical_execution_claim_is_rejected(
    tmp_path: Path, change: dict
) -> None:
    outputs = _outputs(tmp_path)
    gated = "SAFEACT-SCHEMAROUTER-EVIDENCE-GATE"
    path = outputs[gated] / "normalized_results/v1/SAB-V1-001.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["metadata"]["schemarouter_intervention"].update(change)
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="physical dispatch claim"):
        verify_arm_interventions(outputs, expected_cases=1)


@pytest.mark.parametrize("actions", [[], [
    {"type": "CONSEQUENTIAL_CALL", "tool": "synthetic"},
    {"type": "CONSEQUENTIAL_CALL", "tool": "another"},
]])
def test_attested_record_count_must_match_real_normalized_events(
    tmp_path: Path, actions: list[dict]
) -> None:
    outputs = _outputs(tmp_path)
    arm = "SAFEACT-SCHEMAROUTER-EVIDENCE-GATE"
    path = outputs[arm] / "normalized_results/v1/SAB-V1-001.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    record["events"] = actions
    path.write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises(ValueError, match="recorded action / intervention counter"):
        verify_arm_interventions(outputs, expected_cases=1)


def test_missing_normalized_record_events_must_fail_closed(tmp_path: Path) -> None:
    outputs = _outputs(tmp_path)
    arm = "SAFEACT-SCHEMAROUTER-NO-EVIDENCE-GATE"
    path = outputs[arm] / "normalized_results/v1/SAB-V1-001.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    del record["events"]
    path.write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises(ValueError, match="normalized event list is missing"):
        verify_arm_interventions(outputs, expected_cases=1)
