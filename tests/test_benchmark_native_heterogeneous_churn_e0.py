"""B1: real mixed-source registry churn and live-scope parity, E0 only."""

from __future__ import annotations

from dataclasses import replace
from types import MappingProxyType

import pytest

from schemarouter import AuthorizationPolicy, SchemaRouter
from schemarouter.native_graph_index import NativeSchemaGraphIndex
from schemarouter.native_semantic_index import NativeSchemaPostingIndex
from scripts import benchmark_native_heterogeneous_churn_e0 as churn


@pytest.mark.parametrize("registered_routes", (500, 5000))
def test_original_native_journal_matches_fresh_rebuild_across_source_churn(
    registered_routes: int,
) -> None:
    """Changing the registered source must invalidate stale snapshots."""
    report = churn.audit_heterogeneous_churn(registered_routes)
    assert report["evidence_tier"] == churn.EVIDENCE
    assert report["registered_source_routes"] == registered_routes
    assert report["source_type_count"] == 4
    assert report["journal_and_full_rebuild_exact_parity"] is True
    assert report["stale_index_rejections"] == 2
    assert report["source_snapshot_count"] == 3
    assert report["revoked_source_excluded"] is True
    assert report["restored_source_reincluded"] is True
    assert report["registry_version_count"] == 3
    assert report["paired_checks"] == 3 * 4 * 4 * 3 * 2
    assert report["source_authorization_oracle_checked"] is True
    assert report["policy_and_principal_checks"] > 0
    assert report["same_predicate_health_flip_checks"] >= 3 * 2
    assert report["independent_e2_qualified"] is False
    assert report["source_gold_verified"] is False
    assert report["default_routing_changed"] is False
    assert report["query_wall_ms"]["p99"] >= 0
    assert report["query_process_cpu_ms"]["p50"] >= 0
    assert report["peak_process_rss_kib"] > 0
    assert "gold" not in str(report.get("samples", ""))
    assert "case_ids" not in report
    assert "route_ids" not in report


@pytest.mark.parametrize("bad", (0, 499, 5001, True, "5000"))
def test_churn_only_allows_preregistered_native_catalog_sizes(bad: object) -> None:
    with pytest.raises(ValueError, match="500/5000"):
        churn.audit_heterogeneous_churn(bad)  # type: ignore[arg-type]


@pytest.mark.parametrize("bad", (0, 5, False, 2.5))
def test_churn_refuses_invalid_sample_count(bad: object) -> None:
    with pytest.raises(ValueError, match="iterations"):
        churn.audit_heterogeneous_churn(500, iterations=bad)  # type: ignore[arg-type]


def test_churn_refuses_forged_oracle_even_when_index_and_rebuild_agree(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Do not mistake two matching indexes for independent ground truth."""
    monkeypatch.setattr(churn, "original_heterogeneous_oracle", lambda *a: ())
    with pytest.raises(AssertionError, match="original-source"):
        churn.audit_heterogeneous_churn(500)


def test_churn_refuses_stale_journal_instead_of_approving_changed_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A broken delta must never qualify as a fresh source snapshot."""
    monkeypatch.setattr(
        churn.NativeSchemaGraphIndex,
        "refresh_from_inmemory_journal",
        classmethod(lambda cls, previous, registry: previous),
    )
    with pytest.raises(AssertionError, match="journal"):
        churn.audit_heterogeneous_churn(500)


def test_churn_refuses_common_mode_unprivileged_policy_leak(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An oracle and an index sharing the same broken policy are not gold."""

    def accidentally_public_scope(router: SchemaRouter, scenario: str) -> None:
        router.authorization_policy = AuthorizationPolicy(default_effect="allow")
        router.planner.availability_predicate = None

    monkeypatch.setattr(churn, "configure_heterogeneous_scope", accidentally_public_scope)
    with pytest.raises(AssertionError, match="unprivileged"):
        churn.audit_heterogeneous_churn(500)


def test_churn_refuses_common_mode_hidden_field_leak(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Source and index agreeing on a leaked hidden field is still a failure."""
    real_scope = churn.configure_heterogeneous_scope

    def accidentally_unhidden_scope(router: SchemaRouter, scenario: str) -> None:
        real_scope(router, "visible" if scenario == "hidden" else scenario)

    monkeypatch.setattr(churn, "configure_heterogeneous_scope", accidentally_unhidden_scope)
    with pytest.raises(AssertionError, match="scope"):
        churn.audit_heterogeneous_churn(500)


def test_journal_equivalence_rejects_corrupted_unqueried_route_locations() -> None:
    """A graph with altered unrelated routes cannot pass source parity."""
    router = churn.build_heterogeneous_fixture(500)
    fresh = NativeSchemaGraphIndex.build(
        NativeSchemaPostingIndex.build(router.registry),
    )
    locations = dict(fresh.field_index.route_locations)
    assert "unrelated_00000.read" in locations
    locations["unrelated_00000.read"] = ("unrelated_00001", "read")
    poisoned = replace(
        fresh,
        field_index=replace(
            fresh.field_index,
            route_locations=MappingProxyType(locations),
        ),
    )
    with pytest.raises(AssertionError, match="source snapshot"):
        churn._verify_snapshot_equivalence(poisoned, fresh)
