"""Contract tests for bounded, no-execution authorized phase diagnostics."""
from __future__ import annotations

import pytest

from benchmarks.current_adapter_field_scope_dev_v1 import principal
from benchmarks.current_adapter_scaled_authorized_dev_v1 import build_fixture
from scripts.research_authorized_retrieval_phase_profile import (
    LANGUAGES,
    SCOPES,
    STAGE_METHODS,
    WIDTHS,
    _percentile,
    profile,
    timed_retrieve,
)


def test_scoped_current_router_phases_and_no_scope_control() -> None:
    router, policy = build_fixture(100)
    who = principal("viewer")
    restricted = timed_retrieve(
        router, query="invoice total amount", role="viewer",
        width=24, mode="field_scope",
    )
    assert restricted["total_ms"] >= 0
    assert restricted["phases_ms"]["scoped_registry_rebuild"] > 0
    assert len(restricted["ids_sha256"]) == 64
    assert restricted["unauthorized_count"] == 0
    assert restricted["principal"] == who.roles[0]
    assert all(
        name in restricted["phases_ms"] for _, _, name in STAGE_METHODS
    )
    assert policy.default_effect == "deny"

    from schemarouter import AuthorizationPolicy, SchemaRouter

    no_scope = SchemaRouter(
        registry=router.registry,
        authorization_policy=AuthorizationPolicy(
            rules=policy.rules, default_effect=policy.default_effect,
        ),
    )
    plain = timed_retrieve(
        no_scope, query="invoice total amount", role="viewer",
        width=24, mode="route_policy_only",
    )
    assert plain["phases_ms"]["scoped_registry_rebuild"] == 0
    assert plain["unauthorized_count"] == 0
    assert plain["total_ms"] >= 0


def test_instrumentation_restores_original_methods_after_calls() -> None:
    from schemarouter import SchemaRouter
    from schemarouter.planner import SchemaPlanner

    methods = [(cls, name, getattr(cls, name)) for cls, name, _ in STAGE_METHODS]
    router, _ = build_fixture(100)
    timed_retrieve(
        router, query="get total invoice", role="editor",
        width=56, mode="field_scope",
    )
    for cls, name, original in methods:
        assert getattr(cls, name) is original
    assert SchemaRouter is not SchemaPlanner


def test_rejects_unbounded_cpu_runs_without_scoring() -> None:
    bad = [
        {"sizes": (50,)}, {"sizes": (100, 100)},
        {"sizes": (True,)}, {"sizes": []},
        {"repeats": 0}, {"repeats": 3},
        {"languages": ("fr",)}, {"languages": ("en", "en")},
        {"widths": (12,)}, {"widths": (56, 56)},
    ]
    for kwargs in bad:
        with pytest.raises(ValueError):
            profile(**kwargs)
    for values in ([], [-1.0], [float("nan")], [float("inf")]):
        with pytest.raises(ValueError):
            _percentile(values, 95)


def test_one_scale_paired_auth_request_matrix() -> None:
    result = profile(
        sizes=(100,), repeats=1,
        languages=(LANGUAGES[0],), widths=(WIDTHS[0],),
    )
    assert result["cases_actual"] == result["cases_expected"] == 4
    assert len(result["groups"]) == 4
    assert result["scope"]["automatic_product_change"] is False
    assert result["scope"]["may_release"] is False
    assert result["scope"]["independent_confirmation"] is False
    for item in result["cases"]:
        assert item["mode"] in SCOPES
        assert item["unauthorized_count"] == 0
        assert item["size"] == 100
