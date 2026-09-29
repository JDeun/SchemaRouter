"""Frozen deterministic adaptive-shortlist policy for #430 research.

This module is research-only. It does not change SchemaRouter's public retrieval API
or execution authority. The policy chooses how many already-ranked candidates from a
Top-10 retrieval pool are exposed to the downstream agent.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import TypeVar

POLICY_NAME = "largest-adjacent-gap-v1"
MIN_K = 3
MAX_K = 10

T = TypeVar("T")


def largest_gap_depth(
    scores: Sequence[float],
    *,
    min_k: int = MIN_K,
    max_k: int = MAX_K,
) -> int:
    """Choose a deterministic query-relative shortlist depth.

    Rules:
    - consider at most the first max_k already-ranked scores;
    - scores must be finite and non-increasing;
    - if fewer than min_k candidates exist, expose all available candidates;
    - find the largest adjacent score drop;
    - if every adjacent drop is zero, expose the full considered pool;
    - when the largest drop occurs at multiple positions, choose the later cut
      (recall-first tie break);
    - clamp the chosen cut to at least min_k.

    No learned parameter or score threshold is used.
    """

    if isinstance(min_k, bool) or not isinstance(min_k, int) or min_k < 1:
        raise ValueError("min_k must be an integer >= 1")
    if isinstance(max_k, bool) or not isinstance(max_k, int) or max_k < min_k:
        raise ValueError("max_k must be an integer >= min_k")

    considered = [float(score) for score in scores[:max_k]]
    if not considered:
        return 0

    if any(not math.isfinite(score) for score in considered):
        raise ValueError("adaptive shortlist scores must be finite")

    for left, right in zip(considered, considered[1:]):
        if left < right:
            raise ValueError(
                "adaptive shortlist scores must already be ranked non-increasingly"
            )

    if len(considered) <= min_k:
        return len(considered)

    gaps = [
        left - right
        for left, right in zip(considered, considered[1:])
    ]
    largest_gap = max(gaps)
    if largest_gap <= 0.0:
        return len(considered)

    # Positions are one-based candidate counts after which the cut would occur.
    # Recall-first tie break: use the latest equally large gap.
    cut = max(
        position
        for position, gap in enumerate(gaps, start=1)
        if gap == largest_gap
    )
    return min(len(considered), max(min_k, cut))


def slice_adaptive(
    candidates: Sequence[T],
    scores: Sequence[float],
    *,
    min_k: int = MIN_K,
    max_k: int = MAX_K,
) -> list[T]:
    """Return the policy-selected prefix of an already-ranked candidate list."""

    if len(candidates) != len(scores):
        raise ValueError("candidates and scores must have the same length")
    depth = largest_gap_depth(scores, min_k=min_k, max_k=max_k)
    return list(candidates[:depth])
