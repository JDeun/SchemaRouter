"""Prospective Japanese-script lexical regression, with wholly synthetic queries.

Does NOT reproduce, score, train on, or tune the frozen #432/#424 tasks.
"""
from __future__ import annotations

import pytest

from schemarouter import (
    EndpointSpec,
    FieldSpec,
    InMemoryRegistry,
    PlanRequest,
    SchemaPlanner,
    ToolSpec,
)
from schemarouter.planner import _tokens


def test_kana_kanji_and_legacy_korean_ascii_tokens():
    assert {"論文", "を", "検索", "する"}.issubset(_tokens("論文を検索する"))
    assert {"物性", "データ", "を", "確認"}.issubset(
        _tokens("物性データを確認")
    )
    assert "カタログ" in _tokens("カタログ")
    assert "論文" in _tokens("論文")
    assert "열전도율" in _tokens("열전도율을")
    assert "thermal" in _tokens("thermal")


def synthetic_registry(*, japanese_alias: bool) -> InMemoryRegistry:
    registry = InMemoryRegistry()
    registry.register(ToolSpec(
        name="a_unrelated",
        description="Inventory locations",
        endpoints=[EndpointSpec(
            name="fetch", description="Get a location",
            read_only=True, output_fields=[
                FieldSpec(name="location_id", semantic_id="location.id"),
            ],
        )],
    ))
    registry.register(ToolSpec(
        name="z_properties",
        description="Numeric material property readings",
        endpoints=[EndpointSpec(
            name="read", description="Read a property",
            read_only=True, output_fields=[
                FieldSpec(
                    name="thermal_conductivity",
                    semantic_id="material.thermal_conductivity",
                    aliases=["熱伝導率"] if japanese_alias else [],
                ),
            ],
        )],
    ))
    return registry


@pytest.mark.parametrize("indexed", [False, True])
def test_declared_japanese_field_alias_scores_above_unrelated_route(indexed):
    registry = synthetic_registry(japanese_alias=True)
    planner = SchemaPlanner(registry, candidate_index=indexed)
    request = PlanRequest(query="熱伝導率を確認")
    intent = planner.analyzer.analyze(request, registry)
    scored = planner._semantic_recall_catalog(request, intent)
    scores = {
        f"{candidate.tool.key}.{candidate.endpoint.name}": candidate.score
        for candidate in scored
    }
    assert scores["z_properties.read"] > scores["a_unrelated.fetch"]
    assert scores["z_properties.read"] > 0


@pytest.mark.parametrize("indexed", [False, True])
def test_untranslated_english_only_catalog_gets_no_invented_match(indexed):
    registry = synthetic_registry(japanese_alias=False)
    planner = SchemaPlanner(registry, candidate_index=indexed)
    request = PlanRequest(query="熱伝導率を確認")
    intent = planner.analyzer.analyze(request, registry)
    scored = planner._semantic_recall_catalog(request, intent)
    scores = {
        f"{candidate.tool.key}.{candidate.endpoint.name}": candidate.score
        for candidate in scored
    }
    assert scores["z_properties.read"] == scores["a_unrelated.fetch"] == 0
