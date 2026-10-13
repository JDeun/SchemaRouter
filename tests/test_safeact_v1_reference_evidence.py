"""Guard against accidentally presenting SafeAct reference simulator as model results."""

import json
from pathlib import Path


def test_official_reference_file_cannot_claim_agent_metrics() -> None:
    manifest = json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "benchmarks/safeact-v1-official-reference-20261008.json"
        ).read_text(encoding="utf-8")
    )
    assert manifest["mode"] == "simulate"
    assert manifest["reference_cases_evaluated"] == 131
    assert manifest["reference_cases_scored"] == 131
    assert manifest["agent_executions"] == 0
    assert manifest["model_calls"] == 0
    assert manifest["reported_agent_metrics"] is None
    assert manifest["reported_treatment_effect"] is None
    assert len(manifest["not_valid_for"]) >= 3
