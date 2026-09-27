from __future__ import annotations

import inspect
import math
from collections.abc import Awaitable, Callable, Iterable, Mapping
from typing import Any, Literal

from .decisions import (
    DecisionEvidence,
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
        min_score_by_option: Mapping[str, float] | None = None,
        min_margin_by_option: Mapping[str, float] | None = None,
        threshold_application: Literal["filter_then_rank", "rank_then_gate"] = "filter_then_rank",
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
        self.min_score_by_option = self._validate_threshold_map(
            min_score_by_option,
            name="min_score_by_option",
        )
        self.min_margin_by_option = self._validate_threshold_map(
            min_margin_by_option,
            name="min_margin_by_option",
        )
        if threshold_application not in {"filter_then_rank", "rank_then_gate"}:
            raise ValueError(
                "threshold_application must be 'filter_then_rank' or 'rank_then_gate'"
            )
        self.threshold_application = threshold_application
        self.option_text = option_text or self._default_option_text

    @staticmethod
    def _validate_threshold_map(
        values: Mapping[str, float] | None,
        *,
        name: str,
    ) -> dict[str, float]:
        if values is None:
            return {}
        if not isinstance(values, Mapping):
            raise TypeError(f"{name} must be a mapping or None")

        normalized: dict[str, float] = {}
        for option_id, raw_threshold in values.items():
            if not isinstance(option_id, str) or not option_id.strip():
                raise ValueError(f"{name} keys must be non-empty strings")
            if (
                not isinstance(raw_threshold, (int, float))
                or isinstance(raw_threshold, bool)
            ):
                raise TypeError(f"{name} values must be numeric")
            threshold = float(raw_threshold)
            if not math.isfinite(threshold) or not 0.0 <= threshold <= 1.0:
                raise ValueError(
                    f"{name} values must be finite and between 0 and 1"
                )
            normalized[option_id] = threshold
        return normalized

    def _score_threshold_for(self, option_id: str) -> float:
        return self.min_score_by_option.get(option_id, self.min_score)

    def _margin_threshold_for(self, option_id: str) -> float:
        return self.min_margin_by_option.get(option_id, self.min_margin)

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

        evidence = [
            DecisionEvidence(
                kind=str(request.context.get("surface") or "pairwise_ranking"),
                state=(
                    "match"
                    if score >= self._score_threshold_for(request.options[index].id)
                    else "no_match"
                ),
                source="pairwise-score",
                option_id=request.options[index].id,
                score=score,
                score_kind="pairwise_probability",
                metadata={
                    "threshold": self._score_threshold_for(request.options[index].id),
                },
            )
            for index, score in ranked
        ]

        top_index, top_score = ranked[0]
        top_option_id = request.options[top_index].id
        top_effective_min_score = self._score_threshold_for(top_option_id)
        top_effective_min_margin = self._margin_threshold_for(top_option_id)
        second_score = ranked[1][1] if len(ranked) > 1 else None
        top_margin = (
            top_score - second_score
            if second_score is not None
            else None
        )
        metadata: dict[str, Any] = {
            "provider": "pairwise-score",
            "option_count": len(request.options),
            "min_score": self.min_score,
            "min_margin": self.min_margin,
            "score_kind": "pairwise",
            "threshold_application": self.threshold_application,
            "top_option_id": top_option_id,
            "top_effective_min_score": top_effective_min_score,
            "top_effective_min_margin": top_effective_min_margin,
            "top_score": top_score,
            "second_score": second_score,
            "top_margin": top_margin,
            "ranked_options": [
                {
                    "option_id": request.options[index].id,
                    "score": score,
                }
                for index, score in ranked
            ],
        }

        if self.threshold_application == "rank_then_gate":
            if request.max_selections != 1:
                raise PlanningError(
                    "rank_then_gate threshold application supports only "
                    "single-selection decisions"
                )
            if top_score < top_effective_min_score:
                return validate_decision(
                    request,
                    DecisionResult(
                        abstained=True,
                        evidence=evidence,
                        metadata={**metadata, "reason": "top_below_min_score"},
                    ),
                )
            if (
                top_effective_min_margin > 0.0
                and top_margin is not None
                and top_margin < top_effective_min_margin
            ):
                return validate_decision(
                    request,
                    DecisionResult(
                        abstained=True,
                        evidence=evidence,
                        metadata={
                            **metadata,
                            "effective_boundary_min_margin": (
                                top_effective_min_margin
                            ),
                            "boundary_margin": top_margin,
                            "reason": "ambiguous_selection_boundary",
                        },
                    ),
                )
            return validate_decision(
                request,
                DecisionResult(
                    selections=[
                        DecisionSelection(
                            option_id=top_option_id,
                            score=top_score,
                        )
                    ],
                    evidence=evidence,
                    metadata=metadata,
                ),
            )

        eligible = [
            item
            for item in ranked
            if item[1] >= self._score_threshold_for(request.options[item[0]].id)
        ]
        if not eligible:
            return validate_decision(
                request,
                DecisionResult(
                    abstained=True,
                    evidence=evidence,
                    metadata={**metadata, "reason": "below_min_score"},
                ),
            )

        limit = min(request.max_selections, len(eligible))
        selected = eligible[:limit]
        if len(eligible) > limit:
            boundary_option_id = request.options[selected[-1][0]].id
            effective_min_margin = self._margin_threshold_for(boundary_option_id)
            metadata["effective_boundary_min_margin"] = effective_min_margin
            boundary_margin = selected[-1][1] - eligible[limit][1]
            metadata["boundary_margin"] = boundary_margin
            if effective_min_margin > 0.0 and boundary_margin < effective_min_margin:
                return validate_decision(
                    request,
                    DecisionResult(
                        abstained=True,
                        evidence=evidence,
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
                evidence=evidence,
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
