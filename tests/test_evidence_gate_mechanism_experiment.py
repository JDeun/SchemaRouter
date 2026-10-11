"""Regression coverage for the real EvidenceGate eight-case controlled run."""

import copy
import json
from pathlib import Path

import pytest

from scripts.run_evidence_gate_mechanism_experiment import (
    _attempt_action,
    run_cases,
)


def _fixture() -> dict:
    return json.loads(
        Path("benchmarks/evidence-to-action-v1/cases.json").read_text(
            encoding="utf-8"
        )
    )


def test_full_real_gate_matches_frozen_seed() -> None:
    actual = run_cases(_fixture())
    frozen = json.loads(
        Path("benchmarks/evidence-to-action-v1/baseline-results.json").read_text(
            encoding="utf-8"
        )
    )
    assert {
        name: arm["metrics"] for name, arm in actual["conditions"].items()
    } == frozen
    assert actual["official_safeact_v1"] is False
    assert actual["model_calls"] == 0


def test_hidden_gold_label_cannot_be_passed_to_runtime_gate() -> None:
    case = _fixture()["cases"][1]
    with pytest.raises(ValueError, match="evaluator-only"):
        _attempt_action(case, "schemarouter_evidence_gate")
    runtime = {k: v for k, v in case.items() if k != "expected_action"}
    assert _attempt_action(runtime, "schemarouter_evidence_gate") is False


def test_live_observation_type_mismatch_is_denied() -> None:
    case = _fixture()["cases"][5]
    runtime = {k: v for k, v in case.items() if k != "expected_action"}
    assert _attempt_action(runtime, "schemarouter_evidence_gate") is False
    supported = copy.deepcopy(runtime)
    supported["available_source_type"] = "experimental"
    assert _attempt_action(supported, "schemarouter_evidence_gate") is True


def test_undeclared_condition_fails_closed() -> None:
    case = _fixture()["cases"][0]
    runtime = {k: v for k, v in case.items() if k != "expected_action"}
    with pytest.raises(ValueError, match="unknown"):
        _attempt_action(runtime, "fake_evidence_gate")
