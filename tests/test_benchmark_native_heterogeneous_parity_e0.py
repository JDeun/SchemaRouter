"""#1560: source-native mixed-source index parity (developer E0 only)."""

from __future__ import annotations

import pytest

from schemarouter import PrincipalContext
from schemarouter.concept_graph_retrieval import retrieve_authorized_concept_graph
from schemarouter.errors import PolicyViolationError
from schemarouter.native_graph_index import NativeSchemaGraphIndex
from schemarouter.native_semantic_index import NativeSchemaPostingIndex
from scripts.benchmark_native_heterogeneous_parity_e0 import (
    ACTOR,
    CASES,
    CATALOG,
    audit_heterogeneous,
    build_heterogeneous_fixture,
    configure_heterogeneous_scope,
    original_heterogeneous_oracle,
)


@pytest.mark.parametrize("registered_routes", (500, 5000))
def test_all_four_native_source_types_resolve_exact_original_routes(registered_routes):
    """Catch false matches when postings include mixed-source near aliases."""
    router = build_heterogeneous_fixture(registered_routes)
    index = NativeSchemaGraphIndex.build(NativeSchemaPostingIndex.build(router.registry))
    assert index.field_index.indexed_route_count == registered_routes
    assert len({tool.source_type for tool in router.registry.tools()}) >= 4
    configure_heterogeneous_scope(router, "visible")
    for case in CASES:
        assert original_heterogeneous_oracle(router, case.concept_id, ACTOR) == (
            case.route_id,
        )
        for query in case.aliases:
            result = retrieve_authorized_concept_graph(
                router, query, principal=ACTOR, catalog=CATALOG,
                index=index, experimental_indexed_direct=True,
            )
            assert result.status == "complete"
            assert result.route_ids == (case.route_id,)
            assert result.executable_authority is False
            assert result.independent_quality_evidence is False


@pytest.mark.parametrize("scenario,concept_id", [
    ("hidden", "mcp.document"),
    ("denied", "openapi.temperature"),
    ("unavailable", "optimade.formula"),
])
def test_policy_scope_health_excludes_correct_typed_source(scenario, concept_id):
    """Catch an indexed result leaking a hidden, denied or sick source."""
    router = build_heterogeneous_fixture(500)
    index = NativeSchemaGraphIndex.build(NativeSchemaPostingIndex.build(router.registry))
    configure_heterogeneous_scope(router, scenario)
    assert original_heterogeneous_oracle(router, concept_id, ACTOR) == ()
    case = next(c for c in CASES if c.concept_id == concept_id)
    result = retrieve_authorized_concept_graph(
        router, case.aliases[0], principal=ACTOR, catalog=CATALOG,
        index=index, experimental_indexed_direct=True,
    )
    assert result.status == "no_proven_hit"
    assert result.route_ids == ()
    assert result.independent_quality_evidence is False


def test_registered_schema_change_rejects_stale_snapshot_then_rebuilds():
    """Catch publishing stale original-source evidence after a tool mutation."""
    router = build_heterogeneous_fixture(500)
    index = NativeSchemaGraphIndex.build(NativeSchemaPostingIndex.build(router.registry))
    configure_heterogeneous_scope(router, "visible")
    case = next(c for c in CASES if c.concept_id == "custom.sku")
    tool = router.registry.get("custom_inventory")
    tool.license = "revoked-license"
    router.registry.register(tool, replace=True)
    with pytest.raises(PolicyViolationError):
        retrieve_authorized_concept_graph(
            router, case.aliases[0], principal=ACTOR, catalog=CATALOG,
            index=index, experimental_indexed_direct=True,
        )
    fresh = NativeSchemaGraphIndex.build(NativeSchemaPostingIndex.build(router.registry))
    assert original_heterogeneous_oracle(router, case.concept_id, ACTOR) == ()
    current = retrieve_authorized_concept_graph(
        router, case.aliases[0], principal=ACTOR, catalog=CATALOG,
        index=fresh, experimental_indexed_direct=True,
    )
    assert current.route_ids == ()
    assert current.status == "no_proven_hit"


@pytest.mark.parametrize("bad", (0, 499, 5001, True, "5000"))
def test_audit_refuses_unregistered_catalogue_sizes(bad):
    with pytest.raises(ValueError, match="500/5000"):
        build_heterogeneous_fixture(bad)


def test_audit_refuses_forged_untrusted_identity_or_tiny_sample():
    with pytest.raises(ValueError):
        audit_heterogeneous(500, iterations=0)
    router = build_heterogeneous_fixture(500)
    configure_heterogeneous_scope(router, "visible")
    anonymous = PrincipalContext(subject="anonymous", roles=())
    assert original_heterogeneous_oracle(
        router, "openapi.temperature", anonymous,
    ) == ()


def test_audit_reports_bounded_e0_parity_without_quality_claims():
    report = audit_heterogeneous(500, iterations=2)
    assert report["registered_source_routes"] == 500
    assert report["source_type_count"] == 4
    assert report["independent_e2_qualified"] is False
    assert report["source_gold_verified"] is False
    assert report["default_routing_changed"] is False
    assert report["all_exact_parity"] is True
    assert report["paired_checks"] == 4 * 3 * 4 * 2
    assert report["query_wall_ms"]["p95"] >= 0
    assert report["query_process_cpu_ms"]["p99"] >= 0
