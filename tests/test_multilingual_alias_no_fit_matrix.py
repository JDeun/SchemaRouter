"""Prospective synthetic six-language alias/no-fit regressions (#1339).

No frozen #432/#424 task texts, scores, thresholds, or task identities.
Lexical evidence is not calibrated agent-level no-fit or task success.
"""

from __future__ import annotations

import unicodedata

import pytest

from schemarouter import (
    EndpointSpec,
    InMemoryRegistry,
    PlanRequest,
    SchemaPlanner,
    ToolSpec,
)

ALIASES = (
    "lookup property",
    "물성조회",
    "物性検索",
    "buscar propiedad",
    "Materialwerte suchen",
)
SUPPORTED_QUERIES = (
    "lookup property",
    "물성조회",
    "物性検索",
    "buscar propiedad",
    "Materialwerte suchen",
    "物性検索 schema_unknown",
)
UNSUPPORTED_QUERIES = (
    "pay the bill",
    "로그인 암호 변경",
    "航空券の予約",
    "reservar hotel",
    "überweise geld",
    "機能を削除 unknown_id",
)


def _registry(*, aliases: bool) -> InMemoryRegistry:
    registry = InMemoryRegistry()
    registry.register(
        ToolSpec(
            name="a_warehouse",
            description="Track furniture inventory",
            endpoints=[
                EndpointSpec(
                    name="count",
                    description="Count desks and chairs",
                    read_only=True,
                )
            ],
        )
    )
    registry.register(
        ToolSpec(
            name="z_measurement",
            description="Get numeric sample records",
            endpoints=[
                EndpointSpec(
                    name="fetch",
                    description="Fetch signed sample values",
                    read_only=True,
                    operation_aliases=list(ALIASES) if aliases else [],
                )
            ],
        )
    )
    return registry


def _scores(query: str, *, indexed: bool, aliases: bool) -> dict[str, float]:
    registry = _registry(aliases=aliases)
    planner = SchemaPlanner(registry, candidate_index=indexed)
    request = PlanRequest(query=query)
    intent = planner.analyzer.analyze(request, registry)
    return {
        f"{candidate.tool.key}.{candidate.endpoint.name}": candidate.score
        for candidate in planner._semantic_recall_catalog(request, intent)
    }


@pytest.mark.parametrize("query", SUPPORTED_QUERIES)
def test_declared_language_alias_has_index_parity(query: str) -> None:
    exhaustive = _scores(query, indexed=False, aliases=True)
    indexed = _scores(query, indexed=True, aliases=True)
    assert indexed == exhaustive
    assert exhaustive["z_measurement.fetch"] > 0
    assert exhaustive["z_measurement.fetch"] > exhaustive["a_warehouse.count"]


@pytest.mark.parametrize("query", SUPPORTED_QUERIES)
def test_undeclared_translation_is_not_invented(query: str) -> None:
    for indexed in (False, True):
        scored = _scores(query, indexed=indexed, aliases=False)
        assert scored["z_measurement.fetch"] == 0
        assert scored["a_warehouse.count"] == 0


@pytest.mark.parametrize("query", UNSUPPORTED_QUERIES)
def test_unrelated_query_has_zero_positive_lexical_evidence(query: str) -> None:
    for indexed in (False, True):
        scored = _scores(query, indexed=indexed, aliases=True)
        assert scored["z_measurement.fetch"] == 0
        assert scored["a_warehouse.count"] == 0


@pytest.mark.parametrize("query", ["ﾃﾞｰﾀ", "ｶﾀｶﾅ"])
@pytest.mark.parametrize("indexed", [False, True])
def test_halfwidth_katakana_matches_only_declared_fullwidth_alias(
    query: str, indexed: bool
) -> None:
    aliases = {"ﾃﾞｰﾀ": "データ", "ｶﾀｶﾅ": "カタカナ"}
    registry = InMemoryRegistry()
    registry.register(
        ToolSpec(
            name="sample_records",
            description="Unrelated English labels",
            endpoints=[
                EndpointSpec(
                    name="read",
                    description="Read signed records",
                    read_only=True,
                    operation_aliases=[aliases[query]],
                )
            ],
        )
    )
    planner = SchemaPlanner(registry, candidate_index=indexed)
    request = PlanRequest(query=query)
    intent = planner.analyzer.analyze(request, registry)
    scores = {
        f"{c.tool.key}.{c.endpoint.name}": c.score
        for c in planner._semantic_recall_catalog(request, intent)
    }
    assert scores["sample_records.read"] > 0


@pytest.mark.parametrize("indexed", [False, True])
def test_halfwidth_katakana_is_not_an_invented_translation(indexed: bool) -> None:
    registry = _registry(aliases=False)
    planner = SchemaPlanner(registry, candidate_index=indexed)
    request = PlanRequest(query="ﾃﾞｰﾀ")
    intent = planner.analyzer.analyze(request, registry)
    scores = {
        f"{c.tool.key}.{c.endpoint.name}": c.score
        for c in planner._semantic_recall_catalog(request, intent)
    }
    assert all(score == 0 for score in scores.values())


@pytest.mark.parametrize("indexed", [False, True])
def test_korean_canonical_decomposition_matches_declared_alias(
    indexed: bool,
) -> None:
    composed = "물성조회"
    decomposed = unicodedata.normalize("NFD", composed)
    assert decomposed != composed

    scores = _scores(decomposed, indexed=indexed, aliases=True)
    assert scores["z_measurement.fetch"] > 0
    assert scores["z_measurement.fetch"] > scores["a_warehouse.count"]
    no_declared_alias = _scores(decomposed, indexed=indexed, aliases=False)
    assert all(score == 0 for score in no_declared_alias.values())


@pytest.mark.parametrize("indexed", [False, True])
def test_decomposed_declared_korean_alias_matches_composed_query(
    indexed: bool,
) -> None:
    registry = InMemoryRegistry()
    registry.register(ToolSpec(
        name="sample_records",
        description="Unrelated English text",
        endpoints=[EndpointSpec(
            name="fetch",
            description="Read trusted records",
            read_only=True,
            operation_aliases=[unicodedata.normalize("NFD", "물성조회")],
        )],
    ))
    planner = SchemaPlanner(registry, candidate_index=indexed)
    request = PlanRequest(query="물성조회")
    intent = planner.analyzer.analyze(request, registry)
    scores = {
        f"{candidate.tool.key}.{candidate.endpoint.name}": candidate.score
        for candidate in planner._semantic_recall_catalog(request, intent)
    }
    assert scores["sample_records.fetch"] > 0


def test_unicode_normalization_never_rewrites_original_request() -> None:
    query = unicodedata.normalize("NFD", "물성조회")
    original = PlanRequest(query=query)
    _scores(query, indexed=True, aliases=True)
    assert original.query == query


@pytest.mark.parametrize(
    ("query", "alias"),
    [
        ("カﾞ", "ガ"),
        ("キﾞ", "ギ"),
        ("はﾟ", "ぱ"),
    ],
)
@pytest.mark.parametrize("indexed", [False, True])
def test_mixed_width_kana_mark_matches_canonically_equivalent_alias(
    query: str, alias: str, indexed: bool,
) -> None:
    registry = InMemoryRegistry()
    registry.register(ToolSpec(
        name="kana_records",
        description="Unrelated English metadata",
        endpoints=[EndpointSpec(
            name="search", description="Read one record", read_only=True,
            operation_aliases=[alias],
        )],
    ))
    planner = SchemaPlanner(registry, candidate_index=indexed)
    request = PlanRequest(query=query)
    intent = planner.analyzer.analyze(request, registry)
    ranked = planner._semantic_recall_catalog(request, intent)
    assert {x.tool.key: x.score for x in ranked}["kana_records"] > 0

    # The lexical fold never mutates the original user request nor
    # invents an alias for an English-only metadata surface.
    assert request.query == query
    english = _scores(query, indexed=indexed, aliases=False)
    assert all(score == 0 for score in english.values())
