from __future__ import annotations

import inspect
import math
from collections.abc import Awaitable, Callable, Iterable
from typing import Any

from .decisions import (
    DecisionOption,
    DecisionOptionTextCallable,
    DecisionRequest,
    DecisionResult,
    DecisionSelection,
    validate_decision,
)
from .errors import PlanningError

PairwiseScoreCallable = Callable[
    [list[tuple[str, str]]],
    Iterable[float] | Awaitable[Iterable[float]],
]


class _PairwiseAwaitable:
    """Awaitable pairwise-score result that can release an unconsumed coroutine."""

    def __init__(
        self,
        backend: PairwiseDecisionBackend,
        request: DecisionRequest,
        raw: Awaitable[Iterable[float]],
    ) -> None:
        self._backend = backend
        self._request = request
        self._raw = raw

    def __await__(self):  # type: ignore[no-untyped-def]
        async def resolve() -> DecisionResult:
            return self._backend._result(self._request, await self._raw)

        return resolve().__await__()

    def close(self) -> None:
        close = getattr(self._raw, "close", None)
        if callable(close):
            close()


class PairwiseDecisionBackend:
    """Bounded decision backend driven by query-option pair scores.

    The scorer receives one (query, option_text) pair for every locally
    authorized option and must return one confidence score in [0, 1] for
    every pair. SchemaRouter ranks those scores locally and maps positions
    back to the original opaque option IDs.

    Option metadata is not forwarded by default. A custom option_text
    callback is trusted application code and controls its own disclosure.
    Execution authority never leaves the bounded DecisionRequest.
    """

    def __init__(
        self,
        scorer: PairwiseScoreCallable,
        *,
        min_score: float = 0.0,
        min_margin: float = 0.0,
        option_text: DecisionOptionTextCallable | None = None,
    ) -> None:
        if not callable(scorer):
            raise TypeError("scorer must be callable")
        if not math.isfinite(min_score) or not 0.0 <= min_score <= 1.0:
            raise ValueError("min_score must be finite and between 0 and 1")
        if not math.isfinite(min_margin) or not 0.0 <= min_margin <= 1.0:
            raise ValueError("min_margin must be finite and between 0 and 1")
        self.scorer = scorer
        self.min_score = min_score
        self.min_margin = min_margin
        self.option_text = option_text or self._default_option_text

    @staticmethod
    def _default_option_text(option: DecisionOption) -> str:
        label = option.label.strip() or option.id
        description = option.description.strip()
        return f"{label}\n{description}" if description else label

    @staticmethod
    def _coerce_scores(
        raw: Iterable[float],
        *,
        expected_count: int,
    ) -> list[float]:
        try:
            values = list(raw)
        except TypeError as exc:
            raise PlanningError("pairwise scorer returned a non-iterable batch") from exc
        if len(values) != expected_count:
            raise PlanningError(
                "pairwise scorer returned the wrong number of scores: "
                f"expected {expected_count}, got {len(values)}"
            )

        scores: list[float] = []
        for index, raw_score in enumerate(values):
            try:
                score = float(raw_score)
            except (TypeError, ValueError) as exc:
                raise PlanningError(
                    f"pairwise scorer returned an invalid score at index {index}"
                ) from exc
            if not math.isfinite(score):
                raise PlanningError("pairwise scorer returned a non-finite score")
            if not 0.0 <= score <= 1.0:
                raise PlanningError(
                    "pairwise scorer returned a score outside the required [0, 1] range"
                )
            scores.append(score)
        return scores

    def _result(
        self,
        request: DecisionRequest,
        raw: Iterable[float],
    ) -> DecisionResult:
        scores = self._coerce_scores(raw, expected_count=len(request.options))
        ranked = sorted(
            enumerate(scores),
            key=lambda item: (-item[1], item[0]),
        )
        eligible = [item for item in ranked if item[1] >= self.min_score]

        second_score = ranked[1][1] if len(ranked) > 1 else None
        top_margin = (
            ranked[0][1] - second_score
            if second_score is not None
            else None
        )
        metadata: dict[str, Any] = {
            "provider": "pairwise-score",
            "option_count": len(request.options),
            "min_score": self.min_score,
            "min_margin": self.min_margin,
            "top_score": ranked[0][1],
            "second_score": second_score,
            "top_margin": top_margin,
        }
        if not eligible:
            return validate_decision(
                request,
                DecisionResult(
                    abstained=True,
                    metadata={**metadata, "reason": "below_min_score"},
                ),
            )

        limit = min(request.max_selections, len(eligible))
        selected = eligible[:limit]
        if self.min_margin > 0.0 and len(eligible) > limit:
            boundary_margin = selected[-1][1] - eligible[limit][1]
            metadata["boundary_margin"] = boundary_margin
            if boundary_margin < self.min_margin:
                return validate_decision(
                    request,
                    DecisionResult(
                        abstained=True,
                        metadata={
                            **metadata,
                            "reason": "ambiguous_selection_boundary",
                        },
                    ),
                )

        return validate_decision(
            request,
            DecisionResult(
                selections=[
                    DecisionSelection(
                        option_id=request.options[index].id,
                        score=score,
                    )
                    for index, score in selected
                ],
                metadata=metadata,
            ),
        )

    def decide(
        self,
        request: DecisionRequest,
    ) -> DecisionResult | Awaitable[DecisionResult]:
        pairs = [
            (request.query, self.option_text(option))
            for option in request.options
        ]
        if any(
            not isinstance(query, str)
            or not query.strip()
            or not isinstance(option_text, str)
            or not option_text.strip()
            for query, option_text in pairs
        ):
            raise PlanningError("pairwise decision text must be a non-empty string")

        raw = self.scorer(pairs)
        if inspect.isawaitable(raw):
            return _PairwiseAwaitable(self, request, raw)
        return self._result(request, raw)
