"""Deterministic E5 adapter regressions; no model downloads or frozen task data."""
from __future__ import annotations

import math

import pytest

from schemarouter import (
    DecisionOption,
    DecisionRequest,
    E5CachedEmbedder,
    EmbeddingDecisionBackend,
    EndpointSpec,
    InMemoryRegistry,
    PlanRequest,
    PlanningError,
    SchemaPlanner,
    ToolSpec,
    choose_sync,
)


def test_e5_prefix_and_repeated_option_embedding_cache() -> None:
    batches: list[list[str]] = []

    def encoder(texts: list[str]) -> list[list[float]]:
        batches.append(list(texts))
        return [
            [1.0, 0.0] if text.startswith("query: ") else [0.9, 0.1]
            for text in texts
        ]

    embed = E5CachedEmbedder(encoder, max_cached_passages=2)
    first = embed(["물성을 검색", "Find material properties", "Find publications"])
    second = embed(["材料物性を検索", "Find material properties", "Find publications"])
    third = embed(["Search", "Find material properties", "Find inventory"])

    assert len(first) == len(second) == len(third) == 3
    assert batches == [
        [
            "query: 물성을 검색",
            "passage: Find material properties",
            "passage: Find publications",
        ],
        ["query: 材料物性を検索"],
        ["query: Search", "passage: Find inventory"],
    ]
    assert first[1:] == second[1:]
    assert len(embed._passages) == 2


def test_same_option_text_encoded_only_once_within_batch() -> None:
    batches: list[list[str]] = []

    def encoder(texts: list[str]) -> list[list[float]]:
        batches.append(texts)
        return [[1.0, 0.0] for _ in texts]

    embed = E5CachedEmbedder(encoder, max_cached_passages=0)
    assert len(embed(["한국어", "same", "same"])) == 3
    assert batches == [["query: 한국어", "passage: same"]]
    assert not embed._passages


@pytest.mark.parametrize("cache_limit", [-1, True, 50001, 1.5])
def test_invalid_cache_limits_rejected(cache_limit: object) -> None:
    with pytest.raises(ValueError, match="max_cached_passages"):
        E5CachedEmbedder(lambda _: [], max_cached_passages=cache_limit)  # type: ignore[arg-type]


@pytest.mark.parametrize("bad_texts", [[], [" "], ["query", ""], ["query", 3]])
def test_invalid_text_is_never_encoded(bad_texts: list[object]) -> None:
    invoked = []

    def encoder(texts: list[str]) -> list[list[float]]:
        invoked.append(texts)
        return [[1.0]]

    with pytest.raises(PlanningError, match="non-empty"):
        E5CachedEmbedder(encoder)(bad_texts)  # type: ignore[arg-type]
    assert invoked == []


def test_invalid_encoder_batch_is_not_cached() -> None:
    runs = 0

    def encoder(texts: list[str]) -> list[list[float]]:
        nonlocal runs
        runs += 1
        if runs == 1:
            return [[1.0, 0.0], [math.nan, 1.0]]
        return [[1.0, 0.0] for _ in texts]

    embed = E5CachedEmbedder(encoder)
    with pytest.raises(PlanningError, match="non-finite"):
        embed(["query", "passage"])
    assert not embed._passages
    embed(["query", "passage"])
    assert runs == 2


def test_cached_dimensions_are_rechecked_against_fresh_query() -> None:
    runs = 0

    def encoder(texts: list[str]) -> list[list[float]]:
        nonlocal runs
        runs += 1
        return [[1.0, 0.0] for _ in texts] if runs == 1 else [[1.0, 0.0, 0.0]]

    embed = E5CachedEmbedder(encoder)
    embed(["query", "passage"])
    with pytest.raises(PlanningError, match="inconsistent cached dimensions"):
        embed(["another query", "passage"])


def _catalog() -> InMemoryRegistry:
    registry = InMemoryRegistry()
    registry.register(
        ToolSpec(
            name="materials",
            description="Laboratory material property lookup",
            endpoints=[
                EndpointSpec(
                    name="search",
                    description="Search material properties and band gaps",
                    read_only=True,
                )
            ],
        )
    )
    registry.register(
        ToolSpec(
            name="flights",
            description="Airline flight booking service",
            endpoints=[
                EndpointSpec(
                    name="search",
                    description="Search for available airline flights",
                    read_only=True,
                )
            ],
        )
    )
    return registry


@pytest.mark.parametrize(
    "query",
    ["재료 물성 조사", "材料物性を調べる", "search material properties"],
)
def test_multilingual_embedding_recovers_english_only_candidate_with_opt_in(query: str) -> None:
    registry = _catalog()

    # Deliberately synthetic vectors: tests routing and language-agnostic
    # integration, not actual multilingual encoder quality or recall rates.
    def encoder(texts: list[str]) -> list[list[float]]:
        return [
            [1.0, 0.0] if text.startswith("query: ") or "materials." in text
            else [-1.0, 0.0]
            for text in texts
        ]

    backend = EmbeddingDecisionBackend(
        E5CachedEmbedder(encoder),
        min_similarity=0.5,  # Fixture boundary, NOT a deployed threshold.
    )
    planner = SchemaPlanner(
        registry, candidate_recall_backend=backend,
        candidate_recall_limit=1,
    )
    request = PlanRequest(query=query)
    intent = planner.analyzer.analyze(request, registry)
    lexical_catalog = planner._semantic_recall_catalog(request, intent)

    if query != "search material properties":
        assert all(item.score == 0 for item in lexical_catalog)

    recovered, _ = planner._augment_candidates_with_semantic_recall_sync(
        request, intent, [],
    )
    assert len(recovered) == 1
    assert recovered[0].tool.name == "materials"
    assert recovered[0].selection_source == "semantic_recall"


def test_unrelated_query_abstains_without_creating_candidate() -> None:
    registry = _catalog()

    def encoder(texts: list[str]) -> list[list[float]]:
        return [[0.0, 1.0] if text.startswith("query: ") else [1.0, 0.0]
                for text in texts]

    planner = SchemaPlanner(
        registry,
        candidate_recall_backend=EmbeddingDecisionBackend(
            E5CachedEmbedder(encoder),
            min_similarity=0.5,  # Synthetic negative control only.
        ),
        candidate_recall_limit=1,
    )
    request = PlanRequest(query="은행 계좌 이체해 줘")
    intent = planner.analyzer.analyze(request, registry)
    recovered, notes = planner._augment_candidates_with_semantic_recall_sync(
        request, intent, [],
    )
    assert recovered == []
    assert any("abstained" in note for note in notes)


def test_model_receives_no_decision_option_private_metadata() -> None:
    batches: list[list[str]] = []

    def encoder(texts: list[str]) -> list[list[float]]:
        batches.append(texts)
        return [[1.0, 0.0], [1.0, 0.0]]

    result = choose_sync(
        EmbeddingDecisionBackend(E5CachedEmbedder(encoder)),
        DecisionRequest(
            query="물성",
            options=[DecisionOption(
                id="option:0", label="materials.search",
                description="Search material properties",
                metadata={"secret": "DO_NOT_EXPOSE"},
            )],
        ),
    )
    assert result.selections[0].option_id == "option:0"
    assert "DO_NOT_EXPOSE" not in repr(batches)
