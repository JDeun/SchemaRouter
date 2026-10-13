"""Regression tests for unscored official V1 completion-marker identity audit."""

import json
from pathlib import Path

import pytest

from examples.external_validation.safeact_v1.completion_audit import (
    audit_v1_completions,
)
from examples.external_validation.safeact_v1.run_plan import CONDITIONS, V1RunPlan


def _plans(root: Path) -> list[V1RunPlan]:
    return [
        V1RunPlan(c, root, "frozen-model", f"python3 agent_{i}.py")
        for i, c in enumerate(CONDITIONS)
    ]


def _marker(plan: V1RunPlan, case_id: str) -> dict:
    return {
        "schema_version": 1,
        "case_id": case_id,
        "protocol": "v1",
        "inputs": {
            "case_id": case_id,
            "protocol": "v1",
            "runtime_identity": {
                "mode": "external_agent",
                "allow_shell": False,
                "agent_cmd": plan.agent_command,
                "requested_model": plan.model,
            },
        },
        "observed_runtime_identity": {
            "runtime_model": plan.model,
            "fresh_session": True,
            "session_persistence": "ephemeral",
        },
    }


def _write(plan: V1RunPlan, case_id: str, marker: dict) -> Path:
    folder = (
        plan.safeact_root
        / "output"
        / plan.condition.lower()
        / "completions"
        / "v1"
    )
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{case_id}.json"
    path.write_text(json.dumps(marker), encoding="utf-8")
    return path


def test_complete_three_arm_identity_matrix_is_accepted(tmp_path: Path) -> None:
    plans = _plans(tmp_path)
    for plan in plans:
        for case_id in ("SAB-V1-001", "SAB-V1-002"):
            _write(plan, case_id, _marker(plan, case_id))
    result = audit_v1_completions(plans, expected_cases=2)
    assert result["ok"] is True
    assert all(v["cases"] == 2 for v in result["condition_summaries"].values())


def test_actual_runtime_model_drift_fails_closed(tmp_path: Path) -> None:
    plans = _plans(tmp_path)
    for plan in plans:
        marker = _marker(plan, "SAB-V1-001")
        if plan.condition == CONDITIONS[2]:
            marker["observed_runtime_identity"]["runtime_model"] = "wrong-model"
        _write(plan, "SAB-V1-001", marker)
    result = audit_v1_completions(plans, expected_cases=1)
    assert result["ok"] is False
    assert any("runtime identity mismatch" in e for e in result["errors"])


def test_missing_case_or_non_ephemeral_session_is_rejected(tmp_path: Path) -> None:
    plans = _plans(tmp_path)
    for plan in plans:
        _write(plan, "SAB-V1-001", _marker(plan, "SAB-V1-001"))
    marker = _marker(plans[0], "SAB-V1-002")
    marker["observed_runtime_identity"]["session_persistence"] = "persisted"
    _write(plans[0], "SAB-V1-002", marker)
    result = audit_v1_completions(plans, expected_cases=2)
    assert result["ok"] is False
    assert any("identical case IDs" in e for e in result["errors"])
    assert any("runtime identity mismatch" in e for e in result["errors"])


def test_marker_symlink_to_evaluator_file_is_never_read(tmp_path: Path) -> None:
    plans = _plans(tmp_path)
    for plan in plans:
        _write(plan, "SAB-V1-001", _marker(plan, "SAB-V1-001"))
    forbidden = tmp_path / "evaluator-gold.json"
    forbidden.write_text('{"gold_decision": "NEVER_READ"}', encoding="utf-8")
    path = (
        tmp_path / "output" / CONDITIONS[0].lower()
        / "completions" / "v1" / "SAB-V1-002.json"
    )
    path.symlink_to(forbidden)
    report = audit_v1_completions(plans, expected_cases=1)
    assert report["ok"] is False
    assert any("unsafe completion marker path" in e for e in report["errors"])
    assert "NEVER_READ" not in json.dumps(report)


def test_cannot_reduce_required_cases_to_zero(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="positive"):
        audit_v1_completions(_plans(tmp_path), expected_cases=0)
