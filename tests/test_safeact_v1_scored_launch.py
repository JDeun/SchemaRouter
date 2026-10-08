"""Fail-closed scored launch preflight without calling a paid model."""

import hashlib
from pathlib import Path
from unittest.mock import Mock

import pytest

from scripts import run_safeact_v1_scored as launch


def _inputs(tmp_path: Path) -> dict:
    root = tmp_path / "safeact"
    root.mkdir()
    commands = {
        c: f"python3 agent_{i}.py --model same-model"
        for i, c in enumerate(launch.CONDITIONS)
    }
    public = tmp_path / "public"
    public.mkdir()
    return {
        "safeact_root": root,
        "model": "same-model",
        "commands": commands,
        "contracts": {
            "contracts": [{"action": "act", "sources": []}],
            "case_coverage": {
                f"SAB-V1-{i:03d}": "act"
                for i in range(1, launch.EXPECTED_CASES + 1)
            },
        },
        "public_source_root": public,
        "intervention_manifest": {
            "reviewed": True,
            "conditions": {
                c: {
                    "mode": mode,
                    "adapter_commit": "a" * 40,
                    "agent_command_sha256": hashlib.sha256(
                        commands[c].encode("utf-8")
                    ).hexdigest(),
                }
                for c, mode in zip(
                    launch.CONDITIONS, launch.MODES, strict=True
                )
            },
        },
    }


def _mock_public(monkeypatch, sample: dict) -> None:
    monkeypatch.setattr(launch, "verify_sources", lambda *a: [])
    monkeypatch.setattr(
        launch,
        "public_case_ids",
        lambda root: set(sample["contracts"]["case_coverage"]),
    )
    monkeypatch.setattr(
        launch.subprocess,
        "run",
        lambda *args, **kwargs: Mock(stdout=launch.UPSTREAM_REVISION),
    )


def test_complete_frozen_launch_matrix(monkeypatch, tmp_path: Path) -> None:
    sample = _inputs(tmp_path)
    _mock_public(monkeypatch, sample)
    plans = launch.validate_launch(**sample)
    assert len(plans) == 3
    assert plans[2].condition == launch.CONDITIONS[2]


def test_rejects_unreviewed_gated_arm(monkeypatch, tmp_path: Path) -> None:
    sample = _inputs(tmp_path)
    _mock_public(monkeypatch, sample)
    sample["intervention_manifest"]["reviewed"] = False
    with pytest.raises(ValueError, match="review"):
        launch.validate_launch(**sample)


def test_rejects_missing_case_policy(monkeypatch, tmp_path: Path) -> None:
    sample = _inputs(tmp_path)
    _mock_public(monkeypatch, sample)
    sample["contracts"]["case_coverage"].pop("SAB-V1-001")
    # The public listing is frozen separately from the mutable contract.
    monkeypatch.setattr(
        launch,
        "public_case_ids",
        lambda root: {
            f"SAB-V1-{i:03d}" for i in range(1, 132)
        },
    )
    with pytest.raises(ValueError, match="cover 131"):
        launch.validate_launch(**sample)


def test_rejects_unpinned_runtime_model(monkeypatch, tmp_path: Path) -> None:
    sample = _inputs(tmp_path)
    _mock_public(monkeypatch, sample)
    sample["commands"][launch.CONDITIONS[1]] = "python3 agent.py"
    with pytest.raises(ValueError, match="frozen model"):
        launch.validate_launch(**sample)


def test_rejects_wrong_upstream_revision(monkeypatch, tmp_path: Path) -> None:
    sample = _inputs(tmp_path)
    _mock_public(monkeypatch, sample)
    monkeypatch.setattr(
        launch.subprocess, "run", lambda *a, **k: Mock(stdout="wrong")
    )
    with pytest.raises(ValueError, match="revision"):
        launch.validate_launch(**sample)


def test_duplicate_action_contract_is_rejected(monkeypatch, tmp_path: Path) -> None:
    sample = _inputs(tmp_path)
    _mock_public(monkeypatch, sample)
    sample["contracts"]["contracts"].append(
        sample["contracts"]["contracts"][0].copy()
    )
    with pytest.raises(ValueError, match="unique names"):
        launch.validate_launch(**sample)


def test_empty_declared_model_is_rejected(monkeypatch, tmp_path: Path) -> None:
    sample = _inputs(tmp_path)
    _mock_public(monkeypatch, sample)
    sample["model"] = " "
    with pytest.raises(ValueError, match="nonempty"):
        launch.validate_launch(**sample)


def test_rejects_post_review_command_mutation(monkeypatch, tmp_path: Path) -> None:
    sample = _inputs(tmp_path)
    _mock_public(monkeypatch, sample)
    sample["commands"][launch.CONDITIONS[2]] += " --extra-arg=test"
    with pytest.raises(ValueError, match="altered trusted adapter identity"):
        launch.validate_launch(**sample)
