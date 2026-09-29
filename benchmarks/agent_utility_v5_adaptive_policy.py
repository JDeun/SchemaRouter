"""Frozen deterministic adaptive-depth policy kernel for #430."""

from __future__ import annotations

import math
from collections.abc import Sequence

MIN_K = 3
MAX_K = 10
EPSILON = 1e-9
EVALUATED_POSITIONS = tuple(range(MIN_K, MAX_K))

POLICY_THRESHOLDS = {
    "REL-GAP-005": 0.05,
    "REL-GAP-010": 0.10,
    "REL-GAP-020": 0.20,
    "MAX-GAP-010": 0.10,
}
FIXED_POLICIES = {
    "FIXED-3": 3,
    "FIXED-5": 5,
    "FIXED-10": 10,
}


def _validate_top10(scores: Sequence[float]) -> tuple[float, ...]:
    if len(scores) < MAX_K:
        raise ValueError("adaptive depth requires at least ten ranked scores")

    top10 = tuple(float(value) for value in scores[:MAX_K])
    if not all(math.isfinite(value) for value in top10):
        raise ValueError("adaptive depth requires finite ranked scores")

    if any(left < right for left, right in zip(top10, top10[1:], strict=True)):
        raise ValueError("adaptive depth requires scores sorted in non-increasing order")

    return top10


def normalized_adjacent_gaps(scores: Sequence[float]) -> dict[int, float]:
    """Return preregistered positive-affine-invariant gaps for cut ranks 3..9."""

    top10 = _validate_top10(scores)
    span = top10[0] - top10[-1]
    if span <= EPSILON:
        return {position: 0.0 for position in EVALUATED_POSITIONS}

    return {
        position: (top10[position - 1] - top10[position]) / span
        for position in EVALUATED_POSITIONS
    }


def select_candidate_depth(scores: Sequence[float], policy_id: str) -> int:
    """Select K using only the frozen #430 deterministic score-geometry policy."""

    if policy_id in FIXED_POLICIES:
        return FIXED_POLICIES[policy_id]
    if policy_id not in POLICY_THRESHOLDS:
        raise ValueError(f"unknown adaptive depth policy: {policy_id}")

    top10 = _validate_top10(scores)
    if top10[0] - top10[-1] <= EPSILON:
        return MAX_K

    gaps = normalized_adjacent_gaps(top10)
    threshold = POLICY_THRESHOLDS[policy_id]

    if policy_id.startswith("REL-GAP-"):
        for position in EVALUATED_POSITIONS:
            if gaps[position] >= threshold:
                return position
        return MAX_K

    best_position = min(
        EVALUATED_POSITIONS,
        key=lambda position: (-gaps[position], position),
    )
    if gaps[best_position] >= threshold:
        return best_position
    return MAX_K
