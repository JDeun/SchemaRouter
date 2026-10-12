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


def test_jev_output_rejects_activated_tool_outside_native_candidates() -> None:
    payload = _valid_output()
    name = build_jev_input()["catalog"][0]["name"]
    payload["cases"][0]["activated_tools"] = [name]
    with pytest.raises(ValueError, match="shortlisted candidates"):
        validate_jev_output(payload)


@pytest.mark.parametrize("key", ["candidate_tools", "activated_tools"])
def test_jev_output_rejects_duplicate_tool_ids(key: str) -> None:
    payload = _valid_output()
    name = build_jev_input()["catalog"][0]["name"]
    payload["cases"][0]["candidate_tools"] = [name]
    payload["cases"][0][key] = [name, name]
    with pytest.raises(ValueError, match=f"duplicate {key}"):
        validate_jev_output(payload)


@pytest.mark.parametrize("latency", [float("nan"), float("inf"), -0.01, True, "1"])
def test_jev_output_rejects_invalid_latency(latency: object) -> None:
    payload = _valid_output()
    payload["cases"][0]["latency_ms"] = latency
    with pytest.raises(ValueError, match="finite and non-negative"):
        validate_jev_output(payload)


@pytest.mark.parametrize("probability", [float("nan"), float("inf"), -0.01, 1.01, True, "0.7"])
def test_jev_output_rejects_invalid_probabilities(probability: object) -> None:
    payload = _valid_output()
    name = build_jev_input()["catalog"][0]["name"]
    payload["cases"][0]["candidate_tools"] = [name]
    payload["cases"][0]["probabilities"] = {name: probability}
    with pytest.raises(ValueError, match="invalid probability"):
        validate_jev_output(payload)


def test_jev_output_rejects_probabilities_outside_candidates() -> None:
    payload = _valid_output()
    name = build_jev_input()["catalog"][0]["name"]
    payload["cases"][0]["probabilities"] = {name: 0.6}
    with pytest.raises(ValueError, match="shortlisted candidates"):
        validate_jev_output(payload)


def test_jev_output_accepts_bounded_native_candidates_and_probabilities() -> None:
    payload = _valid_output()
    names = [tool["name"] for tool in build_jev_input()["catalog"][:2]]
    payload["cases"][0].update(
        candidate_tools=names,
        activated_tools=[names[1]],
        probabilities={names[0]: 0.2, names[1]: 0.9},
    )
    validate_jev_output(payload)
