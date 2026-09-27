import math
from typing import Any

import pytest

from schemarouter import (
    DecisionOption,
    DecisionRequest,
    PairwiseDecisionBackend,
    PlanningError,
    choose_async,
    choose_sync,
)


def request(*, max_selections: int = 1) -> DecisionRequest:
    return DecisionRequest(
        query="find material band gap",
        options=[
            DecisionOption(
                id="candidate:0",
                label="materials.search",
                description="Search material properties including band gap",
                metadata={"private_note": "do-not-forward"},
            ),
            DecisionOption(
                id="candidate:1",
                label="papers.search",
                description="Search scientific papers",
            ),
            DecisionOption(
                id="candidate:2",
                label="weather.current",
                description="Get current weather",
            ),
        ],
        max_selections=max_selections,
    )


def test_pairwise_backend_selects_best_bounded_option() -> None:
    def score(pairs: list[tuple[str, str]]) -> list[float]:
        assert len(pairs) == 3
        return [0.96, 0.45, 0.02]

    result = choose_sync(PairwiseDecisionBackend(score), request())

    assert result.abstained is False
    assert result.selections[0].option_id == "candidate:0"
    assert result.selections[0].score == pytest.approx(0.96)
    assert result.metadata["provider"] == "pairwise-score"
    assert result.metadata["option_count"] == 3
    assert result.metadata["top_score"] == pytest.approx(0.96)
    assert result.metadata["second_score"] == pytest.approx(0.45)
    assert result.metadata["top_margin"] == pytest.approx(0.51)
    assert [item["option_id"] for item in result.metadata["ranked_options"]] == [
        "candidate:0",
        "candidate:1",
        "candidate:2",
    ]


def test_pairwise_backend_emits_route_local_typed_evidence() -> None:
    result = choose_sync(
        PairwiseDecisionBackend(
            lambda _: [0.80, 0.55, 0.10],
            min_score=0.50,
            min_score_by_option={"candidate:0": 0.85},
        ),
        request(),
    )

    evidence = {item.option_id: item for item in result.evidence}
    assert evidence["candidate:0"].state == "no_match"
    assert evidence["candidate:1"].state == "match"
    assert evidence["candidate:2"].state == "no_match"
    assert evidence["candidate:0"].source == "pairwise-score"
    assert evidence["candidate:0"].score_kind == "pairwise_probability"
    assert evidence["candidate:0"].metadata["threshold"] == pytest.approx(0.85)
    assert evidence["candidate:1"].metadata["threshold"] == pytest.approx(0.50)


def test_pairwise_backend_never_forwards_option_metadata() -> None:
    captured: list[tuple[str, str]] = []

    def score(pairs: list[tuple[str, str]]) -> list[float]:
        captured.extend(pairs)
        return [0.9, 0.2, 0.1]

    choose_sync(PairwiseDecisionBackend(score), request())

    assert "private_note" not in repr(captured)
    assert "do-not-forward" not in repr(captured)
    assert "materials.search" in captured[0][1]
    assert "band gap" in captured[0][1]


def test_pairwise_backend_abstains_below_score_threshold() -> None:
    result = choose_sync(
        PairwiseDecisionBackend(
            lambda _: [0.10, 0.20, 0.30],
            min_score=0.40,
        ),
        request(),
    )

    assert result.abstained is True
    assert result.selections == []
    assert result.metadata["reason"] == "below_min_score"


def test_pairwise_backend_supports_route_local_score_thresholds() -> None:
    backend = PairwiseDecisionBackend(
        lambda _: [0.62, 0.61, 0.10],
        min_score=0.20,
        min_score_by_option={
            "candidate:0": 0.70,
            "candidate:1": 0.60,
        },
    )

    result = choose_sync(backend, request())

    assert result.abstained is False
    assert result.selections[0].option_id == "candidate:1"
    assert result.metadata["top_option_id"] == "candidate:0"
    assert result.metadata["top_effective_min_score"] == pytest.approx(0.70)
    assert result.metadata["score_kind"] == "pairwise"


def test_pairwise_backend_route_local_score_threshold_can_fail_closed() -> None:
    result = choose_sync(
        PairwiseDecisionBackend(
            lambda _: [0.62, 0.30, 0.10],
            min_score=0.20,
            min_score_by_option={"candidate:0": 0.70},
        ),
        request(),
    )

    assert result.abstained is False
    assert result.selections[0].option_id == "candidate:1"


def test_pairwise_backend_supports_route_local_margin_thresholds() -> None:
    backend = PairwiseDecisionBackend(
        lambda _: [0.80, 0.76, 0.10],
        min_margin=0.0,
        min_margin_by_option={"candidate:0": 0.05},
    )

    result = choose_sync(backend, request())

    assert result.abstained is True
    assert result.metadata["reason"] == "ambiguous_selection_boundary"
    assert result.metadata["effective_boundary_min_margin"] == pytest.approx(0.05)
    assert result.metadata["boundary_margin"] == pytest.approx(0.04)


def test_pairwise_backend_falls_back_to_global_route_thresholds() -> None:
    backend = PairwiseDecisionBackend(
        lambda _: [0.80, 0.76, 0.10],
        min_score=0.70,
        min_margin=0.03,
        min_score_by_option={"different-route": 0.99},
        min_margin_by_option={"different-route": 0.99},
    )

    result = choose_sync(backend, request())

    assert result.abstained is False
    assert result.selections[0].option_id == "candidate:0"
    assert result.metadata["top_effective_min_score"] == pytest.approx(0.70)
    assert result.metadata["effective_boundary_min_margin"] == pytest.approx(0.03)


def test_pairwise_backend_abstains_when_selection_boundary_is_ambiguous() -> None:
    result = choose_sync(
        PairwiseDecisionBackend(
            lambda _: [0.80, 0.79, 0.10],
            min_margin=0.05,
        ),
        request(),
    )

    assert result.abstained is True
    assert result.metadata["reason"] == "ambiguous_selection_boundary"
    assert result.metadata["boundary_margin"] == pytest.approx(0.01)


def test_pairwise_backend_supports_bounded_multi_selection() -> None:
    result = choose_sync(
        PairwiseDecisionBackend(lambda _: [0.9, 0.8, 0.1]),
        request(max_selections=2),
    )

    assert [selection.option_id for selection in result.selections] == [
        "candidate:0",
        "candidate:1",
    ]


@pytest.mark.asyncio
async def test_pairwise_backend_supports_async_scorer() -> None:
    async def score(_: list[tuple[str, str]]) -> list[float]:
        return [0.9, 0.2, 0.1]

    result = await choose_async(PairwiseDecisionBackend(score), request())

    assert result.selections[0].option_id == "candidate:0"


def test_sync_path_rejects_async_pairwise_backend() -> None:
    async def score(_: list[tuple[str, str]]) -> list[float]:
        return [0.9, 0.2, 0.1]

    with pytest.raises(PlanningError, match="asynchronous"):
        choose_sync(PairwiseDecisionBackend(score), request())


@pytest.mark.parametrize(
    ("scores", "message"),
    [
        ([0.9, 0.2], "wrong number"),
        ([0.9, math.nan, 0.1], "non-finite"),
        ([0.9, 1.1, 0.1], "outside"),
        ([0.9, -0.1, 0.1], "outside"),
    ],
)
def test_pairwise_backend_fails_closed_on_invalid_scores(
    scores: list[float],
    message: str,
) -> None:
    with pytest.raises(PlanningError, match=message):
        choose_sync(PairwiseDecisionBackend(lambda _: scores), request())


@pytest.mark.parametrize("threshold", [-0.01, 1.01, math.nan, math.inf])
def test_pairwise_score_threshold_must_be_bounded(threshold: float) -> None:
    with pytest.raises(ValueError, match="min_score"):
        PairwiseDecisionBackend(lambda _: [], min_score=threshold)


@pytest.mark.parametrize("margin", [-0.01, 1.01, math.nan, math.inf])
def test_pairwise_margin_must_be_bounded(margin: float) -> None:
    with pytest.raises(ValueError, match="min_margin"):
        PairwiseDecisionBackend(lambda _: [], min_margin=margin)


@pytest.mark.parametrize(
    ("keyword", "value", "error"),
    [
        ("min_score_by_option", {"candidate:0": -0.1}, ValueError),
        ("min_score_by_option", {"candidate:0": 1.1}, ValueError),
        ("min_score_by_option", {"candidate:0": math.nan}, ValueError),
        ("min_margin_by_option", {"candidate:0": -0.1}, ValueError),
        ("min_margin_by_option", {"candidate:0": 1.1}, ValueError),
        ("min_margin_by_option", {"": 0.5}, ValueError),
        ("min_score_by_option", {"candidate:0": True}, TypeError),
    ],
)
def test_pairwise_route_local_thresholds_are_validated(
    keyword: str,
    value: dict[str, object],
    error: type[Exception],
) -> None:
    with pytest.raises(error):
        PairwiseDecisionBackend(lambda _: [], **{keyword: value})


def test_pairwise_backend_rejects_empty_custom_option_text() -> None:
    backend = PairwiseDecisionBackend(
        lambda _: [],
        option_text=lambda _: " ",
    )

    with pytest.raises(PlanningError, match="non-empty string"):
        choose_sync(backend, request())


def test_pairwise_backend_accepts_generator_batches() -> None:
    def score(_: list[tuple[str, str]]) -> Any:
        return iter([0.9, 0.2, 0.1])

    result = choose_sync(PairwiseDecisionBackend(score), request())

    assert result.selections[0].option_id == "candidate:0"
