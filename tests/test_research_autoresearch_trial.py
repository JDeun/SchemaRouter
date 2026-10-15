"""Prove AutoResearch per-trial receipts and scoped rollback semantics."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from scripts import research_autoresearch_trial as trial
from scripts.research_autoresearch_sandbox import SCIENTIFIC_SCOPE


def fake_report(hash_value: str, decision: str) -> dict[str, Any]:
    return {
        "id": "schemarouter-autoresearch-ranking-sandbox-v1",
        "research_scope": SCIENTIFIC_SCOPE.copy(),
        "source_sha256": {trial.EDITABLE: hash_value},
        "evaluated_requests": 144,
        "sizes": [100, 250, 500],
        "scored_k": [3, 5, 10],
        "candidate_pool_k": 24,
        "decision": {
            "decision": decision,
            "top5_required_route_gain": 1 if decision == "KEEP_RESEARCH_CANDIDATE" else 0,
            "can_merge_product_code": False,
            "independent_qualification": False,
        },
    }


def test_report_never_promotes_product_or_unregistered_experiment() -> None:
    good = fake_report("1" * 64, "KEEP_RESEARCH_CANDIDATE")
    assert trial.verdict(good, candidate_hash="1" * 64) == "keep"
    for key, value in (
        ("sizes", [100]),
        ("evaluated_requests", 1),
        ("candidate_pool_k", 500),
        ("research_scope", {}),
        ("source_sha256", {}),
        ("scored_k", [5]),
    ):
        wrong = json.loads(json.dumps(good))
        wrong[key] = value
        with pytest.raises(ValueError):
            trial.verdict(wrong, candidate_hash="1" * 64)
    wrong = json.loads(json.dumps(good))
    wrong["decision"]["can_merge_product_code"] = True
    with pytest.raises(ValueError):
        trial.verdict(wrong, candidate_hash="1" * 64)


def setup_local_trial(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    candidate = tmp_path / trial.EDITABLE
    candidate.parent.mkdir(parents=True)
    candidate.write_text("trial edit", encoding="utf-8")
    protected = tmp_path / "protected.py"
    protected.write_text("protected", encoding="utf-8")
    monkeypatch.setattr(trial, "ROOT", tmp_path)
    monkeypatch.setattr(trial, "PROTECTED", ("protected.py",))
    monkeypatch.setattr(trial, "checked_out_candidate_at_head", lambda: b"HEAD control")
    monkeypatch.setattr(trial, "protected_worktree_clean", lambda: True)
    monkeypatch.setattr(
        trial, "_git",
        lambda args: subprocess.CompletedProcess(args, 0, "a" * 40 + "\n", ""),
    )
    return candidate


@pytest.mark.parametrize("status,expected", [
    ("KEEP_RESEARCH_CANDIDATE", "keep"),
    ("DISCARD_OR_REVISE", "discard"),
    ("crash", "crash"),
])
def test_only_rejected_or_crashed_candidate_is_restored(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, status: str, expected: str,
) -> None:
    candidate = setup_local_trial(monkeypatch, tmp_path)
    def run_registered(args: list[str], *, timeout: int = 180):
        if args[1] == "pytest":
            if status == "crash":
                return subprocess.CompletedProcess(args, 4, "", "test crash")
            return subprocess.CompletedProcess(args, 0, "tests passed", "")
        report = fake_report(trial.sha(candidate), status)
        output = Path(args[-1])
        output.write_text(json.dumps(report), encoding="utf-8")
        return subprocess.CompletedProcess(args, 0, "scored", "")

    monkeypatch.setattr(trial, "run_registered", run_registered)
    result = trial.execute_one_trial(tmp_path / "artifacts", description="bounded trial")
    assert result["status"] == expected
    assert result["may_release"] is False
    assert result["may_promote_product"] is False
    if expected == "keep":
        assert candidate.read_text() == "trial edit"
        assert result["restored_head_candidate"] is False
    else:
        assert candidate.read_text() == "HEAD control"
        assert result["restored_head_candidate"] is True
    receipt = json.loads((tmp_path / "artifacts/last-trial.json").read_text())
    assert receipt["status"] == expected
    history = (tmp_path / "artifacts/experiment-history.jsonl").read_text().splitlines()
    assert len(history) == 1


def test_trial_refuses_protected_uncommitted_evaluator(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    setup_local_trial(monkeypatch, tmp_path)
    monkeypatch.setattr(trial, "protected_worktree_clean", lambda: False)
    with pytest.raises(RuntimeError):
        trial.execute_one_trial(tmp_path / "artifacts", description="tainted")


def test_registered_commands_and_budget_do_not_accept_arbitrary_executables() -> None:
    with pytest.raises(ValueError):
        trial.run_registered(["-m", "pwn_agent", "--release"])
    with pytest.raises(ValueError):
        trial.run_registered(["-m", "pytest", "-q", "test"], timeout=500)
    env = trial.safe_environment()
    assert "GITHUB_TOKEN" not in env
    assert "OPENAI_API_KEY" not in env
    assert "GH_TOKEN" not in env
