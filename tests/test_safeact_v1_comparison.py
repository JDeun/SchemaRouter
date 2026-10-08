"""Synthetic checks for the post-run three-arm SafeAct integrity audit."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.verify_safeact_v1_comparison import CONDITIONS, verify_comparison


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def _three(tmp_path: Path) -> dict[str, Path]:
    outputs = {}
    for condition in CONDITIONS:
        root = tmp_path / condition
        outputs[condition] = root
        _write(root / "summary.json", {
            "mode": "external_agent", "agent_cmd": "python3 agent.py",
            "selected_protocols": ["v1"], "failures": [],
            "reused_cases": [], "deferred_cases": [], "new_cases_run": 1,
            "dataset_id": "dataset", "dataset_version": "v1",
            "evaluation_contract": "official",
            "metrics": {
                "selected_cases": 1, "scored_cases": 1,
                "evaluated_cases": 1, "harness_excluded_cases": 0,
                "strict_success_rate": 0.5,
            },
        })
        artifacts = {}
        for name in (
            "public_scenario", "raw_output", "trace",
            "normalized_record", "evaluation_record",
        ):
            rel = f"{name}/v1/SAB-V1-001.json"
            file = root / rel
            entry = {"case_id": "SAB-V1-001"}
            if name == "trace":
                entry.update({
                    "runtime_model": "model-a", "fresh_session": True,
                    "session_persistence": "ephemeral",
                })
            _write(file, entry)
            artifacts[name] = {
                "path": rel,
                "sha256": hashlib.sha256(file.read_bytes()).hexdigest(),
            }
        _write(root / "completions/v1/SAB-V1-001.json", {
            "protocol": "v1", "schema_version": 1,
            "case_id": "SAB-V1-001",
            "public_scenario_sha256": artifacts["public_scenario"]["sha256"],
            "inputs": {
                "hidden_case_spec_sha256": "frozen-gold-hash",
                "runtime_identity": {"requested_model": "model-a"},
            },
            "observed_runtime_identity": {
                "runtime_model": "model-a", "fresh_session": True,
                "session_persistence": "ephemeral",
            },
            "artifacts": artifacts,
        })
    return outputs


def test_valid_official_three_arm_structure(tmp_path: Path) -> None:
    result = verify_comparison(_three(tmp_path), expected_cases=1)
    assert result["paired_cases"] == 1
    assert result["attested_model"] == "model-a"
    assert "false_refusal_rate" in result["not_measured_here"]


def test_simulator_must_not_be_reported_as_agent(tmp_path: Path) -> None:
    outputs = _three(tmp_path)
    file = outputs[CONDITIONS[0]] / "summary.json"
    data = json.loads(file.read_text(encoding="utf-8"))
    data["mode"] = "simulate"
    _write(file, data)
    with pytest.raises(ValueError, match="simulated run"):
        verify_comparison(outputs, expected_cases=1)


def test_changed_runtime_model_rejected(tmp_path: Path) -> None:
    outputs = _three(tmp_path)
    file = outputs[CONDITIONS[2]] / "completions/v1/SAB-V1-001.json"
    data = json.loads(file.read_text(encoding="utf-8"))
    data["observed_runtime_identity"]["runtime_model"] = "model-b"
    _write(file, data)
    with pytest.raises(ValueError, match="runtime model changed"):
        verify_comparison(outputs, expected_cases=1)


def test_tampered_official_evaluation_rejected(tmp_path: Path) -> None:
    outputs = _three(tmp_path)
    file = outputs[CONDITIONS[1]] / "evaluation_record/v1/SAB-V1-001.json"
    file.write_text("tampered", encoding="utf-8")
    with pytest.raises(ValueError, match="tampered official artifact"):
        verify_comparison(outputs, expected_cases=1)


def test_different_case_fingerprint_rejected(tmp_path: Path) -> None:
    outputs = _three(tmp_path)
    file = outputs[CONDITIONS[2]] / "completions/v1/SAB-V1-001.json"
    data = json.loads(file.read_text(encoding="utf-8"))
    data["inputs"]["hidden_case_spec_sha256"] = "changed"
    _write(file, data)
    with pytest.raises(ValueError, match="different case set"):
        verify_comparison(outputs, expected_cases=1)

def test_rejects_forged_runtime_attestation(tmp_path: Path) -> None:
    outputs = _three(tmp_path)
    root = outputs[CONDITIONS[1]]
    trace = root / "trace/v1/SAB-V1-001.json"
    data = json.loads(trace.read_text(encoding="utf-8"))
    data["runtime_model"] = "forged-model"
    _write(trace, data)
    marker = root / "completions/v1/SAB-V1-001.json"
    value = json.loads(marker.read_text(encoding="utf-8"))
    value["artifacts"]["trace"]["sha256"] = hashlib.sha256(
        trace.read_bytes()
    ).hexdigest()
    _write(marker, value)
    with pytest.raises(ValueError, match="runtime trace attestation mismatch"):
        verify_comparison(outputs, expected_cases=1)


@pytest.mark.parametrize("field", ["reused_cases", "deferred_cases"])
def test_official_run_rejects_reused_or_deferred_case_lists(
    tmp_path: Path, field: str
) -> None:
    outputs = _three(tmp_path)
    path = outputs[CONDITIONS[0]] / "summary.json"
    summary = json.loads(path.read_text(encoding="utf-8"))
    summary[field] = ["SAB-V1-001"]
    _write(path, summary)
    with pytest.raises(ValueError, match="incomplete or simulated run"):
        verify_comparison(outputs, expected_cases=1)


@pytest.mark.parametrize("field", ["reused_cases", "deferred_cases"])
def test_non_list_case_accounting_rejected(
    tmp_path: Path, field: str
) -> None:
    outputs = _three(tmp_path)
    path = outputs[CONDITIONS[1]] / "summary.json"
    summary = json.loads(path.read_text(encoding="utf-8"))
    summary[field] = 0
    _write(path, summary)
    with pytest.raises(ValueError, match="incomplete or simulated run"):
        verify_comparison(outputs, expected_cases=1)
