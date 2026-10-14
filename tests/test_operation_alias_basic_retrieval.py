"""Prospective, synthetic-only checks for explicitly declared operation aliases.

No frozen #432 / #424 queries, task identities or outcome rows are consumed.
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


def registry(*, declare_alias: bool) -> InMemoryRegistry:
    result = InMemoryRegistry()
    result.register(ToolSpec(
        name="a_unrelated",
        description="Track office furniture inventory",
        endpoints=[EndpointSpec(
            name="update",
            description="Change desk quantity",
            read_only=False,
        )],
    ))
    result.register(ToolSpec(
        name="z_documents",
        description="Document records",
        endpoints=[EndpointSpec(
            name="find",
            description="Locate a document record",
            operation_aliases=(
                ["검색", "buscar", "nachschlagen"] if declare_alias else []
            ),
            read_only=True,
        )],
    ))
    return result


def scores(query: str, *, indexed: bool, aliases: bool) -> dict[str, float]:
    instance = registry(declare_alias=aliases)
    planner = SchemaPlanner(instance, candidate_index=indexed)
    request = PlanRequest(query=query)
    intent = planner.analyzer.analyze(request, instance)
    rows = planner._semantic_recall_catalog(request, intent)
    return {
        f"{row.tool.key}.{row.endpoint.name}": row.score
        for row in rows
    }


@pytest.mark.parametrize("indexed", [False, True])
@pytest.mark.parametrize("query", ["검색", "buscar", "nachschlagen"])
def test_declared_language_alias_is_used_in_exhaustive_and_indexed_recall(
    query: str, indexed: bool
):
    matched = scores(query, indexed=indexed, aliases=True)
    assert matched["z_documents.find"] > matched["a_unrelated.update"]
    assert matched["z_documents.find"] > 0


@pytest.mark.parametrize("indexed", [False, True])
@pytest.mark.parametrize("query", ["검색", "buscar", "nachschlagen"])
def test_no_undeclared_translation_or_capability_match(query: str, indexed: bool):
    unmatched = scores(query, indexed=indexed, aliases=False)
    assert unmatched["z_documents.find"] == 0.0
    assert unmatched["a_unrelated.update"] == 0.0


@pytest.mark.parametrize("indexed", [False, True])
@pytest.mark.parametrize("alias_state", [False, True])
def test_unrelated_unsupported_request_cannot_gain_lexical_positive_evidence(
    indexed: bool, alias_state: bool
):
    unrelated = scores("무기 제조", indexed=indexed, aliases=alias_state)
    assert unrelated["z_documents.find"] == 0
    assert unrelated["a_unrelated.update"] == 0
