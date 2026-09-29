from __future__ import annotations

import pytest

from benchmarks.agent_utility_v5_adaptive_policy import (
    EVALUATED_POSITIONS,
    MAX_K,
    normalized_adjacent_gaps,
    select_candidate_depth,
)


def test_normalized_gaps_are_positive_affine_invariant() -> None:
    scores = [10.0, 9.7, 9.4, 8.0, 7.8, 7.6, 7.5, 7.4, 7.3, 7.2]
    transformed = [7.5 * value - 123.4 for value in scores]

    original = normalized_adjacent_gaps(scores)
    shifted = normalized_adjacent_gaps(transformed)

    assert original.keys() == shifted.keys()
    for position in EVALUATED_POSITIONS:
        assert shifted[position] == pytest.approx(original[position])


@pytest.mark.parametrize(
    "policy_id",
    ["REL-GAP-005", "REL-GAP-010", "REL-GAP-020", "MAX-GAP-010"],
)
def test_policy_depth_is_positive_affine_invariant(policy_id: str) -> None:
    scores = [10.0, 9.8, 9.6, 8.1, 8.0, 7.9, 7.7, 7.6, 7.5, 7.4]
    transformed = [0.25 * value + 999.0 for value in scores]

    assert select_candidate_depth(scores, policy_id) == select_candidate_depth(
        transformed,
        policy_id,
    )


def test_relative_policy_uses_first_eligible_cut() -> None:
    scores = [10.0, 9.9, 9.8, 9.1, 9.0, 8.9, 8.8, 8.7, 8.6, 8.5]

    assert select_candidate_depth(scores, "REL-GAP-005") == 3


def test_max_gap_policy_breaks_ties_toward_smaller_k() -> None:
    scores = [10.0, 9.8, 9.6, 9.0, 8.8, 8.2, 8.0, 7.8, 7.6, 7.4]

    assert select_candidate_depth(scores, "MAX-GAP-010") == 3


@pytest.mark.parametrize(
    ("policy_id", "expected"),
    [("FIXED-3", 3), ("FIXED-5", 5), ("FIXED-10", 10)],
)
def test_fixed_controls_are_exact(policy_id: str, expected: int) -> None:
    assert select_candidate_depth([], policy_id) == expected


@pytest.mark.parametrize(
    "policy_id",
    ["REL-GAP-005", "REL-GAP-010", "REL-GAP-020", "MAX-GAP-010"],
)
def test_zero_spread_fails_closed_to_max_k(policy_id: str) -> None:
    assert select_candidate_depth([1.0] * 10, policy_id) == MAX_K


def test_policy_rejects_unsorted_or_nonfinite_scores() -> None:
    with pytest.raises(ValueError, match="non-increasing"):
        select_candidate_depth(
            [10.0, 9.0, 9.5, 8.0, 7.0, 6.0, 5.0, 4.0, 3.0, 2.0],
            "REL-GAP-010",
        )

    with pytest.raises(ValueError, match="finite"):
        select_candidate_depth(
            [10.0, 9.0, 8.0, 7.0, 6.0, float("nan"), 4.0, 3.0, 2.0, 1.0],
            "REL-GAP-010",
        )


def test_policy_rejects_unknown_id_and_short_rankings() -> None:
    with pytest.raises(ValueError, match="unknown"):
        select_candidate_depth([10.0] * 10, "REL-GAP-999")

    with pytest.raises(ValueError, match="at least ten"):
        select_candidate_depth([10.0] * 9, "REL-GAP-010")
