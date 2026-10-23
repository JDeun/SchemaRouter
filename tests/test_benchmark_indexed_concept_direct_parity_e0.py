"""No-model source-oracle controls for opt-in #1560 indexed concept lookup."""
from __future__ import annotations

import pytest

from schemarouter.concept_graph_retrieval import retrieve_authorized_concept_graph
from schemarouter.native_graph_index import NativeSchemaGraphIndex
from schemarouter.native_semantic_index import NativeSchemaPostingIndex
from scripts.benchmark_indexed_concept_direct_parity_e0 import (
    ACTOR,
    ALIASES,
    CASES,
    CATALOG,
    DIRECT_ROUTES,
    build_fixture,
    configure_scope,
    original_source_direct_oracle,
)


def test_indexed_concept_direct_same_registered_source_contract_at_500():
    """Exact pre-K5 count comes from an ORIGINAL source scan outside lookup."""
    router = build_fixture(500)
    index = NativeSchemaGraphIndex.build(NativeSchemaPostingIndex.build(router.registry))
    assert index.field_index.indexed_route_count == 500
    counts = {"one": 1, "six": 6, "none": 0, "hidden": 0, "health": 1}
    for scenario in CASES:
        configure_scope(router, scenario)
        expected = original_source_direct_oracle(router)
        assert len(expected) == counts[scenario]
        if len(expected) == 1:
            assert expected == (DIRECT_ROUTES[0],)
        for query in ALIASES:
            indexed = retrieve_authorized_concept_graph(
                router, query, principal=ACTOR, catalog=CATALOG,
                index=index, experimental_indexed_direct=True,
            )
            original = retrieve_authorized_concept_graph(
                router, query, principal=ACTOR, catalog=CATALOG,
                index=index,
            )
            assert indexed == original
            assert indexed.executable_authority is False
            assert indexed.independent_quality_evidence is False
            if scenario == "six":
                assert indexed.status == "over_k_unranked"
                assert indexed.route_ids == indexed.route_sets == ()
            elif scenario in ("one", "health"):
                assert indexed.route_ids == expected
            else:
                assert indexed.route_ids == (
                    "contact_directory.read", "case_service.read",
                )


@pytest.mark.parametrize("size", (0, 499, 5001, True, "500"))
def test_benchmark_rejects_unregistered_catalogue_sizes(size):
    with pytest.raises(ValueError, match="500/5000"):
        build_fixture(size)


def test_benchmark_rejects_unknown_scenario_without_authorizing():
    router = build_fixture(500)
    with pytest.raises(ValueError, match="unknown predeclared"):
        configure_scope(router, "oracle-gold-refill")
