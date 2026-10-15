"""Prospective synthetic six-language alias/no-fit regressions (#1339).

No frozen #432/#424 task texts, scores, thresholds, or task identities.
Lexical evidence is not calibrated agent-level no-fit or task success.
"""

from __future__ import annotations

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
