import pytest

from scripts.external_validation_jev_contract import (
    PINNED_PI_JEV_COMMIT,
    build_jev_input,
    validate_jev_output,
)


def _valid_output() -> dict:
    handoff = build_jev_input()
    return {
        "schema_version": 1,
        "cases": [
            {
                "id": case["id"],
                "candidate_tools": [],
                "activated_tools": [],
                "latency_ms": 1.0,
                "probabilities": None,
            }
            for case in handoff["cases"]
        ],
    }


def test_jev_handoff_preserves_frozen_surface() -> None:
    handoff = build_jev_input()
    assert handoff["pi_jev_commit"] == PINNED_PI_JEV_COMMIT
    assert handoff["top_k"] == 3
    assert handoff["external_execution"] is False
    assert len(handoff["catalog"]) == 82
    assert len(handoff["cases"]) == 16
    assert len(handoff["catalog_sha256"]) == 64
    assert len(handoff["cases_sha256"]) == 64
    assert "activated_tools" in handoff["return_per_case"]


def test_jev_output_contract_accepts_complete_native_result() -> None:
    validate_jev_output(_valid_output())


def test_jev_output_contract_rejects_missing_case() -> None:
    payload = _valid_output()
    payload["cases"].pop()
    with pytest.raises(ValueError, match="each frozen case exactly once"):
        validate_jev_output(payload)


def test_jev_output_contract_rejects_unknown_tool() -> None:
    payload = _valid_output()
    payload["cases"][0]["activated_tools"] = ["not-a-frozen-tool"]
    with pytest.raises(ValueError, match="unknown activated_tools"):
        validate_jev_output(payload)
