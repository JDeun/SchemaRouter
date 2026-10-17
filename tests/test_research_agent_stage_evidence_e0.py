"""E0 synthetic-only failure witnesses; never a scored multilingual E2 study."""
from __future__ import annotations

import json

import pytest

from scripts.research_agent_stage_evidence_e0 import (
    observed_stages,
    sanitized_e0_jsonl,
    sanitized_e0_trace,
)

SECRET = "RAW-GOLD-SECRET-TO-REDACT"
SOURCE = "a" * 40
DIGEST = "b" * 64
KEY = b"synthetic-only-secret-hmac-key-1234"


def original_row() -> dict:
    return {
        "condition": "EVAL-FIXED5-OPTIN",
        "language": "ko",
        "passed": False,
        "supported": True,
        "task_complete": False,
        "context_overflow": False,
        "initial_required_route_miss": True,
        "initial_miss_recovered": False,
        "candidate_history": [["marine.read"]],
        "attempts": [{
            "route_id": SECRET, "arguments": {"password": SECRET},
            "schema_valid": False, "semantic_valid": False,
            "policy_blocked": False, "expected_at_step": True,
            "advanced_task": False, "error": SECRET,
            "observation": {"private": SECRET},
        }],
        "turn_rows": [{"event": "final", "generated": SECRET}],
        "final_text": SECRET,
        "query": SECRET,
        "required_routes": [SECRET],
        "tool_call_count": 1,
        "input_tokens": 10,
        "tool_schema_tokens": 42,
        "candidate_selection_latency_ms": 1.25,
    }


def trace(row: dict, **changes):
    params = {
        "source_revision": SOURCE, "source_sha256": DIGEST,
        "task_identity": "private-task-" + SECRET,
        "hmac_key": KEY, "seed": 123,
    }
    params.update(changes)
    return sanitized_e0_trace(row, **params)


def test_observed_stages_are_gated_posthoc_and_never_raw_gold():
    raw = original_row()
    safe = trace(raw)
    assert safe["observed_stages"] == [
        "initial_required_route_not_exposed",
        "input_schema_rejection_observed",
        "agent_final_before_task_completion",
    ]
    assert safe["visible_candidate_counts"] == [1]
    assert safe["task_hmac_sha256"] == trace(raw)["task_hmac_sha256"]
    assert safe["independent_e2_qualified"] is False
    assert safe["evidence_tier"] == "E0_SYNTHETIC_DEV_ONLY"
    assert "RAW-GOLD" not in json.dumps(safe)
    assert "route_id" not in json.dumps(safe)
    assert "query" not in json.dumps(safe)
    assert "attempts" not in safe
    assert "final_text" not in safe
    assert raw["attempts"][0]["observation"]["private"] == SECRET
    line = sanitized_e0_jsonl(
        raw, source_revision=SOURCE, source_sha256=DIGEST,
        task_identity="private-task-" + SECRET, hmac_key=KEY, seed=123,
    )
    assert line.endswith("\n") and line.count("\n") == 1
    assert json.loads(line) == safe


def test_unsupported_execution_is_observed_not_mislabeled_model_accuracy():
    raw = original_row()
    raw.update({
        "supported": False,
        "attempts": [{
            "schema_valid": True, "semantic_valid": True,
            "policy_blocked": False, "expected_at_step": False,
            "advanced_task": False, "error": None,
            "arguments": {"secret": SECRET},
        }],
    })
    assert observed_stages(raw) == [
        "unsupported_tool_executed", "unsupported_no_fit_response_mismatch",
    ]


def test_supported_wrong_operation_and_task_argument_failure_are_separate():
    raw = original_row()
    raw["initial_required_route_miss"] = False
    raw["attempts"] = [
        {
            "schema_valid": True, "semantic_valid": True,
            "policy_blocked": False, "expected_at_step": False,
            "advanced_task": False, "error": None,
        },
        {
            "schema_valid": True, "semantic_valid": False,
            "policy_blocked": False, "expected_at_step": True,
            "advanced_task": False, "error": "invalid_task_arguments",
        },
    ]
    assert "wrong_operation_attempt_observed" in observed_stages(raw)
    assert "task_argument_mismatch_observed" in observed_stages(raw)


def test_tool_execution_error_and_policy_block_are_observed_but_not_inferred():
    raw = original_row()
    raw["initial_required_route_miss"] = False
    raw["turn_rows"] = []
    raw["attempts"] = [
        {
            "schema_valid": True, "semantic_valid": True,
            "policy_blocked": False, "expected_at_step": True,
            "advanced_task": False, "error": "provider-is-down:" + SECRET,
        },
        {
            "schema_valid": True, "semantic_valid": False,
            "policy_blocked": True, "expected_at_step": False,
            "advanced_task": False, "error": "destructive_policy_block",
        },
    ]
    assert observed_stages(raw) == [
        "policy_block_observed", "tool_execution_error_observed",
    ]
    assert SECRET not in json.dumps(trace(raw))


def test_passed_task_does_not_produce_failure_cause():
    raw = original_row()
    raw["passed"] = True
    assert observed_stages(raw) == ["passed"]


@pytest.mark.parametrize(("change", "expected"), (
    ({"source_revision": "bad"}, "exact hashes"),
    ({"source_sha256": "bad"}, "exact hashes"),
    ({"hmac_key": b"weak"}, "at least 16"),
    ({"seed": -1}, "invalid E0 seed"),
    ({"seed": True}, "invalid E0 seed"),
))
def test_invalid_provenance_fails_closed(change, expected):
    with pytest.raises(ValueError, match=expected):
        trace(original_row(), **change)


def test_frozen_or_unexpected_conditions_are_never_reclassified():
    raw = original_row()
    raw["condition"] = "SR-5"
    with pytest.raises(ValueError, match="isolated opt-in"):
        trace(raw)


def test_malformed_verdicts_or_oversized_candidate_selection_are_rejected():
    raw = original_row()
    raw["attempts"][0]["schema_valid"] = SECRET
    with pytest.raises(ValueError, match="verdict"):
        trace(raw)
    raw = original_row()
    raw["candidate_history"] = [["a", "b", "c", "d", "e", "f"]]
    with pytest.raises(ValueError, match="fixed-K5"):
        trace(raw)
    raw["candidate_history"] = [["a", "a"]]
    with pytest.raises(ValueError, match="fixed-K5"):
        trace(raw)


def test_nonfinite_latency_never_leaves_as_json():
    raw = original_row()
    raw["candidate_selection_latency_ms"] = float("nan")
    with pytest.raises(ValueError, match="latency"):
        trace(raw)


def test_unclassified_without_direct_stage_evidence():
    raw = original_row()
    raw["initial_required_route_miss"] = False
    raw["attempts"] = []
    raw["turn_rows"] = []
    assert observed_stages(raw) == ["unclassified"]


def test_supported_fixture_completion_without_final_agent_turn_is_not_answer():
    raw = original_row()
    raw.update({
        "supported": True, "passed": True, "task_complete": True,
        "initial_required_route_miss": False,
        "turn_rows": [{"event": "tool_calls", "text": SECRET}],
        "final_text": SECRET,
    })
    safe = trace(raw)
    assert safe["passed"] is True
    assert safe["task_complete"] is True
    assert safe["agent_final_turn_observed"] is False
    assert safe["supported_final_after_fixture_completion_observed"] is False
    assert safe["actual_final_answer_correctness_measured"] is False
    assert SECRET not in json.dumps(safe)


def test_supported_completed_fixture_plus_final_turn_has_structural_not_factual_flag():
    raw = original_row()
    raw.update({
        "supported": True, "passed": True, "task_complete": True,
        "initial_required_route_miss": False,
        "turn_rows": [
            {"event": "tool_calls", "visible_observations": [{"secret": SECRET}]},
            {"event": "final", "text": SECRET},
        ],
        "final_text": SECRET,
    })
    safe = trace(raw)
    assert safe["agent_final_turn_observed"] is True
    assert safe["supported_final_after_fixture_completion_observed"] is True
    assert safe["actual_final_answer_correctness_measured"] is False
    assert "visible_observations" not in safe
    assert SECRET not in json.dumps(safe)


def test_unsupported_refusal_does_not_become_supported_final_answer_success():
    raw = original_row()
    raw.update({
        "supported": False, "passed": True, "task_complete": False,
        "attempts": [], "final_text": "REQUEST_MORE_TOOLS",
        "turn_rows": [{"event": "final", "text": SECRET}],
    })
    safe = trace(raw)
    assert safe["agent_final_turn_observed"] is True
    assert safe["supported_final_after_fixture_completion_observed"] is False
    assert safe["actual_final_answer_correctness_measured"] is False


@pytest.mark.parametrize("bad", (None, "final", {}, [None], [{"event": None}]))
def test_structurally_corrupted_agent_turns_cannot_be_published(bad):
    raw = original_row()
    raw["turn_rows"] = bad
    with pytest.raises(ValueError, match="post-execution agent turn events"):
        trace(raw)
