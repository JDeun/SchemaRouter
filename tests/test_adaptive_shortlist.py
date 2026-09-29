from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from benchmarks.adaptive_shortlist import (
    MAX_K,
    MIN_K,
    POLICY_NAME,
    largest_gap_depth,
    slice_adaptive,
)

ROOT = Path(__file__).resolve().parents[1]
PREREG = ROOT / "benchmarks" / "agent-utility-v5-adaptive-depth-preregistration.json"


def _prereg() -> dict:
    return json.loads(PREREG.read_text(encoding="utf-8"))


def test_adaptive_policy_identity_is_frozen() -> None:
    data = _prereg()
    policy = data["policy"]

    assert data["issue"] == 430
    assert data["status"] == (
        "preregistered_policy_only_execution_blocked_until_b2_terminal"
    )
    assert policy["name"] == POLICY_NAME == "largest-adjacent-gap-v1"
    assert policy["min_k"] == MIN_K == 3
    assert policy["max_k"] == MAX_K == 10
    assert policy["retrieval_pool_k"] == 10
    assert policy["absolute_score_threshold_used"] is False
    assert policy["learned_parameter_used"] is False
    assert data["evaluation_surface"]["execution_authorized_now"] is False


def test_largest_gap_clamps_early_dominant_signal_to_min_k() -> None:
    assert largest_gap_depth([250.0, 6.0, 3.0, 1.5, 0.0]) == 3


def test_largest_gap_selects_query_relative_elbow() -> None:
    assert largest_gap_depth([10.0, 9.0, 8.0, 7.0, 1.0, 0.5]) == 4


def test_largest_gap_uses_recall_first_later_tie() -> None:
    assert largest_gap_depth([10.0, 5.0, 5.0, 5.0, 0.0, 0.0]) == 4


def test_largest_gap_falls_back_to_full_pool_when_scores_are_flat() -> None:
    assert largest_gap_depth([1.0] * 10) == 10


def test_largest_gap_exposes_all_when_fewer_than_min_k_exist() -> None:
    assert largest_gap_depth([2.0, 1.0]) == 2
    assert largest_gap_depth([]) == 0


def test_largest_gap_ignores_candidates_beyond_frozen_max_k() -> None:
    scores = [10.0, 9.0, 8.0, 2.0, 1.0, 0.5, 0.4, 0.3, 0.2, 0.1, -100.0]
    assert largest_gap_depth(scores) == 3


def test_largest_gap_rejects_invalid_score_surfaces() -> None:
    with pytest.raises(ValueError, match="non-increasingly"):
        largest_gap_depth([3.0, 4.0, 2.0])
    with pytest.raises(ValueError, match="finite"):
        largest_gap_depth([3.0, math.nan, 1.0])
    with pytest.raises(ValueError, match="min_k"):
        largest_gap_depth([3.0], min_k=0)
    with pytest.raises(ValueError, match="max_k"):
        largest_gap_depth([3.0], min_k=3, max_k=2)


def test_slice_adaptive_preserves_ranked_prefix_only() -> None:
    candidates = list("abcdefgh")
    scores = [10.0, 9.0, 8.0, 2.0, 1.0, 0.5, 0.25, 0.0]

    assert slice_adaptive(candidates, scores) == ["a", "b", "c"]

    with pytest.raises(ValueError, match="same length"):
        slice_adaptive(["a"], [2.0, 1.0])


def test_adaptive_promotion_gate_is_strictly_predeclared() -> None:
    data = _prereg()
    gate = data["promotion_gate_for_issue_432"]
    independence = data["independence"]

    assert gate["required_tool_set_recall_min"] == 0.97
    assert gate["task_pass_delta_vs_sr5_min"] == -0.02
    assert gate["mean_exposed_candidate_count_must_be_less_than"] == 5.0
    assert gate["tool_schema_tokens_must_be_less_than_sr5"] is True
    assert gate["total_input_tokens_must_not_exceed_sr5"] is True
    assert gate["unauthorized_destructive_executions_max"] == 0
    assert gate["execution_policy_integrity"] == 1

    assert independence["b2_row_content_used_to_choose_policy"] is False
    assert independence["b2_failure_text_used_to_choose_policy"] is False
    assert independence["threshold_sweep_allowed"] is False
    assert independence["post_result_policy_edit_allowed"] is False
