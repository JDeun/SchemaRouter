"""Bounded nested phase instrumentation tests for current public retrieval."""
from __future__ import annotations

import pytest

from benchmarks.current_adapter_field_scope_dev_v1 import principal
from benchmarks.current_adapter_scaled_authorized_dev_v1 import (
    build_fixture,
)
from schemarouter import AuthorizationPolicy, SchemaRouter
from scripts.research_scoped_candidate_hotspot_attribution import (
    STAGES,
    percentile,
    study,
    timed_current_retrieval,
)


def test_actual_scoped_hotspot_counter_separates_projection_and_scorer() -> None:
    router, _ = build_fixture(100)
    data = timed_current_retrieval(
        router, query="parcel ledger payload", role="viewer", mode="scoped",
    )
    assert data["elapsed_ms"] > 0
    assert data["unauthorized_candidates"] == 0
    assert data["stages"]["analysis_registry"]["calls"] == 1
    assert data["stages"]["semantic_catalog"]["calls"] == 1
    assert data["stages"]["field_schema_projection"]["calls"] >= 95
    assert data["stages"]["endpoint_scoring"]["calls"] >= 1
    assert data["stages"]["route_authorization"]["calls"] >= 95


def test_route_policy_control_is_not_field_scope_bypass_in_product() -> None:
    router, policy = build_fixture(100)
    route_control = SchemaRouter(
        registry=router.registry,
        authorization_policy=AuthorizationPolicy(
            rules=policy.rules,
            default_effect=policy.default_effect,
        ),
    )
    control = timed_current_retrieval(
        route_control, query="parcel ledger payload",
        role="viewer", mode="route_policy_only",
    )
    assert control["stages"]["field_schema_projection"]["calls"] == 0
    assert control["stages"]["analysis_registry"]["calls"] == 0
    assert control["unauthorized_candidates"] == 0
    assert policy.visible(
        principal("viewer"),
        next(tool for tool in router.registry.tools() if tool.key == "benchdb"),
        next(tool for tool in router.registry.tools() if tool.key == "benchdb"
             ).endpoints[0],
    )


def test_wrappers_restore_methods_and_scope_after_measurement() -> None:
    methods = [(cls, name, getattr(cls, name)) for cls, name, _ in STAGES]
    router, _ = build_fixture(100)
    timed_current_retrieval(
        router, query="invoice total amount", role="editor", mode="scoped",
    )
    assert all(getattr(cls, name) is old for cls, name, old in methods)


def test_one_catalog_en_language_bounded_paired_attribution() -> None:
    report = study(sizes=(100,), repeats=1, languages=("en",))
    assert report["actual_calls"] == report["expected_calls"] == 4
    assert set(report["groups"]) == {
        "100/scoped", "100/route_policy_only",
    }
    assert report["inclusive_spans_are_overlapping"] is True
    assert report["scope"]["may_release"] is False
    assert all(s["unauthorized_candidates"] == 0 for s in report["samples"])


@pytest.mark.parametrize("bad", (
    {"sizes": (99,)},
    {"sizes": (100, 100)},
    {"sizes": (True,)},
    {"sizes": ()},
    {"repeats": 0},
    {"repeats": 3},
    {"languages": ("fr",)},
    {"languages": ()},
))
def test_unapproved_shapes_rejected_without_evaluating(bad: dict) -> None:
    with pytest.raises(ValueError):
        study(**bad)
    with pytest.raises(ValueError):
        percentile([float("nan")], 95)
