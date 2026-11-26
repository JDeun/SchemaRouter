"""Internal vector validation and cosine math; independent of routing policy."""

from __future__ import annotations

import math
from collections.abc import Iterable

from .errors import PlanningError


def coerce_embedding_vectors(
    raw: Iterable[Iterable[float]],
    *,
    expected_count: int,
) -> list[list[float]]:
    try:
        values = list(raw)
    except TypeError as exc:
        raise PlanningError("embedding backend returned a non-iterable batch") from exc
    if len(values) != expected_count:
        raise PlanningError(
            "embedding backend returned the wrong number of vectors: "
            f"expected {expected_count}, got {len(values)}"
        )

    vectors: list[list[float]] = []
    dimensions: int | None = None
    for index, raw_vector in enumerate(values):
        if isinstance(raw_vector, (str, bytes)):
            raise PlanningError(
                f"embedding backend returned an invalid vector at index {index}"
            )
        try:
            vector = [float(value) for value in raw_vector]
        except (TypeError, ValueError) as exc:
            raise PlanningError(
                f"embedding backend returned an invalid vector at index {index}"
            ) from exc
        if not vector:
            raise PlanningError(
                f"embedding backend returned an empty vector at index {index}"
            )
        if any(not math.isfinite(value) for value in vector):
            raise PlanningError("embedding backend returned a non-finite vector value")
        if dimensions is None:
            dimensions = len(vector)
        elif len(vector) != dimensions:
            raise PlanningError("embedding backend returned inconsistent vector dimensions")
        vectors.append(vector)
    return vectors

def embedding_cosine(left: list[float], right: list[float]) -> float:
    # Squaring an otherwise finite embedding can overflow (or underflow)
    # and make opposite vectors appear maximally similar: min(1, nan)
    # evaluates to 1. Scale each vector before computing either its norm
    # or the dot product, so no unbounded intermediate is constructed.
    left_scale = max(abs(value) for value in left)
    right_scale = max(abs(value) for value in right)
    if left_scale == 0.0 or right_scale == 0.0:
        raise PlanningError("embedding backend returned a zero-norm vector")
    left_scaled = [value / left_scale for value in left]
    right_scaled = [value / right_scale for value in right]
    left_norm = math.sqrt(math.fsum(value * value for value in left_scaled))
    right_norm = math.sqrt(math.fsum(value * value for value in right_scaled))
    value = math.fsum(
        (a / left_norm) * (b / right_norm)
        for a, b in zip(left_scaled, right_scaled, strict=True)
    )
    return max(-1.0, min(1.0, value))
