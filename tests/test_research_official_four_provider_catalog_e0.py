"""Four immutable real publisher sources in one native catalog, E0 only."""
from __future__ import annotations

from collections import Counter

import pytest

from schemarouter.native_graph_index import NativeSchemaGraphIndex


@pytest.fixture(scope="module")
def four_tools() -> tuple:
    from scripts.research_official_four_provider_catalog_e0 import (
        compile_four_original_provider_tools_e0,
    )

    return compile_four_original_provider_tools_e0()


def test_four_original_publishers_in_one_catalog_preserve_methods(four_tools: tuple) -> None:
    from schemarouter import AuthorizationPolicy, PrincipalContext, SchemaRouter

    assert len(four_tools) == 4
    openai, github, ollama, pirate = four_tools
    assert [len(t.endpoints) for t in four_tools] == [355, 651, 2, 1]
    assert len({t.key for t in four_tools}) == 4
    assert Counter(e.method for e in openai.endpoints) == {
        "GET": 161, "POST": 142, "DELETE": 52,
    }
    assert {e.method for e in github.endpoints} == {"GET"}
    assert len({e.name for e in openai.endpoints}) == 355
    assert len({e.name for e in github.endpoints}) == 651

    models = next(e for e in openai.endpoints if e.name == "listModels")
    response = next(e for e in openai.endpoints if e.name == "createResponse")
    deletion = next(e for e in openai.endpoints if e.name == "deleteModel")
    assert models.path == "/models" and models.method == "GET" and models.read_only
    assert response.path == "/responses" and response.method == "POST"
    assert response.execution_metadata["request_body_required"] is True
    assert not response.read_only and not response.destructive
    assert deletion.path == "/models/{model}" and deletion.method == "DELETE"
    assert deletion.destructive and not deletion.read_only
    assert {p.name for p in deletion.parameters if p.required and p.location == "path"} >= {
        "model",
    }

    router = SchemaRouter(authorization_policy=AuthorizationPolicy(default_effect="deny"))
    for tool in four_tools:
        assert tool.source_type is None and tool.license is None
        assert all(not f.semantic_id for e in tool.endpoints for f in e.output_fields)
        router.add_tool(tool)
    assert sum(len(t.endpoints) for t in router.registry.tools()) == 1009
    principal = PrincipalContext(subject="unapproved-four-source-only", roles=())
    predicate = router._authorization_predicate(principal)
    assert predicate is not None
    assert all(not predicate(t, e) for t in four_tools for e in t.endpoints)


@pytest.fixture(scope="module")
def original_four_receipt() -> dict:
    from scripts.research_official_four_provider_catalog_e0 import (
        audit_original_four_provider_native_churn_e0,
    )

    return audit_original_four_provider_native_churn_e0()


def test_real_four_provider_1009_original_routes_have_one_native_index(
    original_four_receipt: dict,
) -> None:
    receipt = original_four_receipt
    assert receipt["original_publisher_count"] == 4
    assert receipt["original_source_route_counts"] == [355, 651, 2, 1]
    assert receipt["original_methods"] == {"GET": 815, "POST": 142, "DELETE": 52}
    assert receipt["mixed_native_route_counts"] == [1009, 358, 1009, 654, 1009]
    assert receipt["registry_versions"] == 5
    assert receipt["index_snapshots"] == 5
    assert receipt["stale_index_rejections"] == 4
    assert receipt["journal_matches_full_rebuild"] is True
    assert receipt["original_source_manifest_matches"] is True
    assert receipt["untrusted_semantic_postings"] == 0
    assert receipt["unreviewed_typed_graph_edges"] == 0
    assert receipt["provider_runtime_calls"] == 0
    assert receipt["execution_authority"] is False
    assert receipt["publisher_gold_verified"] is False
    assert receipt["independent_e2_qualified"] is False
    assert receipt["default_routing_changed"] is False


def test_real_four_provider_churn_records_observed_build_costs(
    original_four_receipt: dict,
) -> None:
    performance = original_four_receipt["performance_observed_not_sla"]
    assert len(performance["full_rebuild_ms"]) == 5
    assert len(performance["journal_refresh_ms"]) == 4
    assert all(value >= 0 for value in performance["full_rebuild_ms"])
    assert all(value >= 0 for value in performance["journal_refresh_ms"])
    assert performance["process_peak_rss_raw"] is None or (
        performance["process_peak_rss_raw"] > 0
    )


def test_four_provider_churn_rejects_forged_noop_journal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.research_official_four_provider_catalog_e0 import (
        audit_original_four_provider_native_churn_e0,
    )

    monkeypatch.setattr(
        NativeSchemaGraphIndex,
        "refresh_from_inmemory_journal",
        classmethod(lambda cls, previous, registry: previous),
    )
    with pytest.raises(ValueError, match="stale|journal|snapshot"):
        audit_original_four_provider_native_churn_e0()
