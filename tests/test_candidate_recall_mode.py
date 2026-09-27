from __future__ import annotations

import pytest

from schemarouter import (
    CallableDecisionBackend,
    EmbeddingDecisionBackend,
    EndpointSpec,
    FieldSpec,
    InMemoryRegistry,
    SchemaPlanner,
    ToolSpec,
)


def _registry() -> InMemoryRegistry:
    registry = InMemoryRegistry()
    for tool_name, endpoint_name, description, field_name in (
        ("weather", "current", "Get current weather and temperature", "temperature"),
        ("materials", "search", "Search material properties including band gap", "band_gap"),
        ("papers", "search", "Search scientific papers by topic", "title"),
        ("finance", "quote", "Get the latest stock market quote", "price"),
    ):
        registry.register(
            ToolSpec(
                name=tool_name,
                description=description,
                endpoints=[
                    EndpointSpec(
                        name=endpoint_name,
                        description=description,
                        read_only=True,
                        output_fields=[FieldSpec(name=field_name)],
                    )
                ],
            )
        )
    return registry


def _material_embedder(texts: list[str]) -> list[list[float]]:
    vectors = [[1.0, 0.0]]
    for text in texts[1:]:
        vectors.append(
            [1.0, 0.0]
            if "materials.search" in text
            else [0.0, 1.0]
        )
    return vectors


def test_candidate_recall_replace_discards_existing_lexical_candidates() -> None:
    seen: dict[str, list[str]] = {}

    def fit(request):
        seen["ids"] = [option.id for option in request.options]
        return {"selections": [{"option_id": request.options[0].id, "score": 0.9}]}

    plan = SchemaPlanner(
        _registry(),
        candidate_recall_backend=EmbeddingDecisionBackend(_material_embedder),
        candidate_recall_limit=1,
        candidate_recall_mode="replace",
        operation_fit_backend=CallableDecisionBackend(fit),
        operation_fit_scope="all_candidates",
        operation_fit_select_accepted=True,
    ).plan("weather 그리고 실리콘 밴드갭")

    assert seen["ids"] == ["materials.search"]
    assert plan.calls[0].tool == "materials"
    assert plan.calls[0].endpoint == "search"
    assert any(
        "semantic candidate recall replaced candidates with 1 selected route"
        in warning
        for warning in plan.warnings
    )


def test_candidate_recall_augment_remains_default() -> None:
    seen: dict[str, list[str]] = {}

    def fit(request):
        seen["ids"] = [option.id for option in request.options]
        material = next(option for option in request.options if option.id == "materials.search")
        return {"selections": [{"option_id": material.id, "score": 0.9}]}

    SchemaPlanner(
        _registry(),
        candidate_recall_backend=EmbeddingDecisionBackend(_material_embedder),
        candidate_recall_limit=1,
        operation_fit_backend=CallableDecisionBackend(fit),
        operation_fit_scope="all_candidates",
        operation_fit_select_accepted=True,
    ).plan("weather 그리고 실리콘 밴드갭")

    assert "weather.current" in seen["ids"]
    assert "materials.search" in seen["ids"]


def test_candidate_recall_replace_failure_retains_lexical_candidates() -> None:
    def fail(_request):
        raise RuntimeError("recall unavailable")

    plan = SchemaPlanner(
        _registry(),
        candidate_recall_backend=CallableDecisionBackend(fail),
        candidate_recall_mode="replace",
    ).plan("current weather")

    assert plan.calls[0].tool == "weather"
    assert any("semantic candidate recall fallback: RuntimeError" in warning for warning in plan.warnings)


@pytest.mark.parametrize("mode", ["strict", "", None])
def test_candidate_recall_mode_rejects_unknown_values(mode) -> None:
    with pytest.raises(ValueError, match="candidate_recall_mode"):
        SchemaPlanner(
            _registry(),
            candidate_recall_mode=mode,  # type: ignore[arg-type]
        )
