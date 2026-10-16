"""Verify instrumented public API and fail-closed CPU budget, without models."""
from __future__ import annotations

import pytest

from benchmarks.current_adapter_scaled_authorized_dev_v1 import build_fixture
from schemarouter import AuthorizationPolicy, SchemaRouter, ToolSpec
from schemarouter.executor import RegistryExecutor
from schemarouter.planner import SchemaPlanner
from scripts.research_availability_fingerprint_attribution import (
    STAGES,
    evaluate,
    sample,
)


def test_instrument_tool_property_restores_after_real_scoped_lookup() -> None:
    original = ToolSpec.fingerprint
    methods = [(target, method, getattr(target, method)) for
               target, method, _ in STAGES]
    router, _ = build_fixture(100)
    item = sample(router, language="en", role="viewer", mode="field_scope")
    assert item["total_ms"] > 0
    assert item["unauthorized_count"] == 0
    assert item["stages"]["access_predicate"]["calls"] > 0
    # No relevant cooldown => no full ToolSpec serialization required.
    assert item["stages"]["tool_fingerprint_resolve"]["calls"] == 0
    assert item["stages"]["cooldown_lookup"]["calls"] == 0
    assert ToolSpec.fingerprint is original
    assert all(getattr(target, method) is method_before
               for target, method, method_before in methods)
    assert RegistryExecutor is not SchemaPlanner


def test_relevant_active_cooldown_still_invokes_fingerprint() -> None:
    router, _ = build_fixture(100)
    router.executor.mark_access_unavailable(
        "benchdb", "probe_db_0005", cooldown_seconds=60.0,
    )
    item = sample(
        router, language="en", role="editor", mode="field_scope",
    )
    assert item["stages"]["tool_fingerprint_resolve"]["calls"] > 0
    assert item["stages"]["cooldown_lookup"]["calls"] > 0
    assert item["unauthorized_count"] == 0


def test_unmodified_route_policy_control_reports_same_real_api() -> None:
    router, policy = build_fixture(100)
    control = SchemaRouter(
        registry=router.registry,
        authorization_policy=AuthorizationPolicy(
            rules=policy.rules, default_effect=policy.default_effect,
        ),
    )
    item = sample(control, language="ja", role="viewer",
                  mode="route_policy_only")
    assert item["stages"]["semantic_catalog"]["calls"] == 1
    assert item["candidate_count"] <= 24
    assert item["unauthorized_count"] == 0


def test_complete_one_size_two_mode_fingerprint_cohort() -> None:
    out = evaluate(sizes=(100,), repeats=1, languages=("en",))
    assert out["expected"] == out["actual"] == 4
    assert set(out["groups"]) == {"100/field_scope", "100/route_policy_only"}
    assert out["nested_times_overlap_do_not_sum"] is True
    assert out["scope"]["may_release"] is False
    assert out["scope"]["independent_confirmation"] is False


@pytest.mark.parametrize("bad", (
    {"sizes": ()}, {"sizes": (101,)}, {"sizes": (100, 100)},
    {"sizes": (True,)}, {"repeats": 0}, {"repeats": 3},
    {"languages": ("fr",)}, {"languages": ("en", "en")},
))
def test_reject_unregistered_source_cpu_shape(bad: dict) -> None:
    with pytest.raises(ValueError):
        evaluate(**bad)
