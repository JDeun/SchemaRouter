import math
from typing import Any

import pytest

from schemarouter import (
    DecisionOption,
    DecisionRequest,
    EmbeddingDecisionBackend,
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


def test_embedding_backend_selects_best_bounded_option() -> None:
    def embed(texts: list[str]) -> list[list[float]]:
        assert len(texts) == 4
        return [
            [1.0, 0.0],
            [0.95, 0.05],
            [0.2, 0.8],
            [-1.0, 0.0],
        ]

    result = choose_sync(EmbeddingDecisionBackend(embed), request())

    assert result.abstained is False
    assert result.selections[0].option_id == "candidate:0"
    assert result.selections[0].score is not None
    assert 0.99 < result.selections[0].score <= 1.0
    assert result.metadata["provider"] == "embedding-similarity"
    assert result.metadata["dimensions"] == 2
    assert result.metadata["top_similarity"] > result.metadata["second_similarity"]
    assert result.metadata["top_margin"] == pytest.approx(
        result.metadata["top_similarity"] - result.metadata["second_similarity"]
    )


def test_embedding_backend_never_forwards_option_metadata() -> None:
    captured: list[str] = []

    def embed(texts: list[str]) -> list[list[float]]:
        captured.extend(texts)
        return [
            [1.0, 0.0],
            [1.0, 0.0],
            [0.0, 1.0],
            [-1.0, 0.0],
        ]

    choose_sync(EmbeddingDecisionBackend(embed), request())

    assert "private_note" not in repr(captured)
    assert "do-not-forward" not in repr(captured)
    assert "materials.search" in captured[1]
    assert "band gap" in captured[1]


def test_embedding_backend_abstains_below_similarity_threshold() -> None:
    def embed(_: list[str]) -> list[list[float]]:
        return [
            [1.0, 0.0],
            [0.0, 1.0],
            [0.0, -1.0],
            [-1.0, 0.0],
        ]

    result = choose_sync(
        EmbeddingDecisionBackend(embed, min_similarity=0.1),
        request(),
    )

    assert result.abstained is True
    assert result.selections == []
    assert result.metadata["reason"] == "below_min_similarity"


def test_embedding_backend_abstains_when_selection_boundary_is_ambiguous() -> None:
    def embed(_: list[str]) -> list[list[float]]:
        return [
            [1.0, 0.0],
            [0.80, 0.60],
            [0.79, 0.61],
            [0.0, 1.0],
        ]

    result = choose_sync(
        EmbeddingDecisionBackend(embed, min_margin=0.05),
        request(),
    )

    assert result.abstained is True
    assert result.metadata["reason"] == "ambiguous_selection_boundary"
    assert result.metadata["boundary_margin"] < 0.05


def test_embedding_backend_supports_bounded_multi_selection() -> None:
    def embed(_: list[str]) -> list[list[float]]:
        return [
            [1.0, 0.0],
            [1.0, 0.0],
            [0.8, 0.6],
            [0.0, 1.0],
        ]

    result = choose_sync(
        EmbeddingDecisionBackend(embed),
        request(max_selections=2),
    )

    assert [selection.option_id for selection in result.selections] == [
        "candidate:0",
        "candidate:1",
    ]


@pytest.mark.asyncio
async def test_embedding_backend_supports_async_embedder() -> None:
    async def embed(_: list[str]) -> list[list[float]]:
        return [
            [1.0, 0.0],
            [0.9, 0.1],
            [0.0, 1.0],
            [-1.0, 0.0],
        ]

    result = await choose_async(EmbeddingDecisionBackend(embed), request())

    assert result.selections[0].option_id == "candidate:0"


def test_sync_path_rejects_async_embedding_backend() -> None:
    async def embed(_: list[str]) -> list[list[float]]:
        return [
            [1.0, 0.0],
            [0.9, 0.1],
            [0.0, 1.0],
            [-1.0, 0.0],
        ]

    with pytest.raises(PlanningError, match="asynchronous"):
        choose_sync(EmbeddingDecisionBackend(embed), request())


@pytest.mark.parametrize(
    ("vectors", "message"),
    [
        ([[1.0], [1.0]], "wrong number"),
        ([[1.0, 0.0], [1.0], [0.0, 1.0], [-1.0, 0.0]], "dimensions"),
        (
            [[1.0, 0.0], [math.nan, 0.0], [0.0, 1.0], [-1.0, 0.0]],
            "non-finite",
        ),
        ([[0.0, 0.0], [1.0, 0.0], [0.0, 1.0], [-1.0, 0.0]], "zero-norm"),
    ],
)
def test_embedding_backend_fails_closed_on_invalid_vectors(
    vectors: list[list[float]],
    message: str,
) -> None:
    with pytest.raises(PlanningError, match=message):
        choose_sync(EmbeddingDecisionBackend(lambda _: vectors), request())


@pytest.mark.parametrize("threshold", [-1.01, 1.01, math.nan, math.inf])
def test_embedding_similarity_threshold_must_be_bounded(threshold: float) -> None:
    with pytest.raises(ValueError, match="min_similarity"):
        EmbeddingDecisionBackend(lambda _: [], min_similarity=threshold)


@pytest.mark.parametrize("margin", [-0.01, 2.01, math.nan, math.inf])
def test_embedding_margin_must_be_bounded(margin: float) -> None:
    with pytest.raises(ValueError, match="min_margin"):
        EmbeddingDecisionBackend(lambda _: [], min_margin=margin)


def test_embedding_backend_rejects_empty_custom_option_text() -> None:
    backend = EmbeddingDecisionBackend(
        lambda _: [],
        option_text=lambda _: " ",
    )

    with pytest.raises(PlanningError, match="non-empty string"):
        choose_sync(backend, request())


def test_embedding_backend_accepts_generator_batches() -> None:
    def embed(_: list[str]) -> Any:
        return iter(
            [
                iter([1.0, 0.0]),
                iter([1.0, 0.0]),
                iter([0.0, 1.0]),
                iter([-1.0, 0.0]),
            ]
        )

    result = choose_sync(EmbeddingDecisionBackend(embed), request())

    assert result.selections[0].option_id == "candidate:0"
