"""E0 dense fork performance cohorts preserve strict K5 and source authority."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from schemarouter import native_fork_index
from schemarouter.native_graph_index import NativeSchemaGraphIndex
from schemarouter.native_semantic_index import NativeSchemaPostingIndex
from scripts.benchmark_native_fork_dense_cpu_e0 import STUDY, benchmark_dense
from scripts.benchmark_native_fork_fieldgroup_e0 import (
    ACTOR,
    ALIASES,
    GROUP,
    _decoy_leaf,
    build_fixture,
)


@pytest.mark.parametrize("fanout", (33, 64))
def test_dense_same_root_benchmark_is_original_source_scoped_and_no_leak(
    fanout: int,
):
    result = benchmark_dense(
        registered_routes=500, extra_status=fanout, iterations=10,
    )
    assert result["study"] == STUDY
    assert result["evidence_tier"].startswith("E0_")
    assert result["registered_base_routes"] == 500
    assert result["registered_native_routes"] == 500 + fanout
    assert result["benchmark_only_original_source_fork_count"] == fanout + 1
    assert result["strict_public_k"] == 5
    assert result["bounded_index_prefork_scheduling"] is True
    assert result["all_aliases_en_ko_ja_match"] is True
    assert result["private_arms_never_exposed"] is True
    assert result["same_source_index_live_health_revocation"] is True
    assert result["dense_over_k"]["status"] == "over_k_unranked"
    assert result["dense_over_k"]["qualified_forks"] == fanout + 1
    assert result["revoked_to_single_fork"]["status"] == "complete"
    assert result["revoked_to_single_fork"]["qualified_forks"] == 1
    assert result["independent_e2_qualified"] is False
    assert result["model_selected_tools"] is False
    assert result["production_slo_qualified"] is False
    assert result["provider_native_http_calls"] == 0
    for condition in ("dense_over_k", "revoked_to_single_fork"):
        for metric in ("wall_ms", "process_cpu_ms"):
            assert all(
                result[condition][metric][p] >= 0
                for p in ("p50", "p95", "p99")
            )


@pytest.mark.parametrize(
    ("routes", "fanout", "iterations"),
    ((499, 33, 10), (500, 32, 10), (500, 65, 10),
     (500, 33, 9), (500, 33, 41), (True, 33, 10),
     (500, True, 10), (500, 33, True)),
)
def test_dense_benchmark_rejects_nonpreregistered_or_unbounded_inputs(
    routes, fanout, iterations,
):
    with pytest.raises(ValueError):
        benchmark_dense(
            registered_routes=routes, extra_status=fanout,
            iterations=iterations,
        )


@pytest.mark.parametrize(("extra", "unsharded_calls", "sharded_calls"), (
    (33, 8, 6),
    (64, 12, 8),
))
def test_bounded_source_index_prefork_shards_skip_redundant_overcap_scan(
    monkeypatch: pytest.MonkeyPatch, extra: int,
    unsharded_calls: int, sharded_calls: int,
):
    """Same original source paths and K5; only duplicate private work differs.

    Count the *actual* inner authorized lookup calls on the identical
    source-native graph. A test-only upper-bound patch disables speculative
    splitting for the baseline, not authorization or hard K limits.
    """
    router = build_fixture(500)
    for i in range(extra):
        router.add_tool(_decoy_leaf(
            f"prefork_extra_status_{i}", "crm.fork_status", "status",
        ))
    index = NativeSchemaGraphIndex.build(
        NativeSchemaPostingIndex.build(router.registry),
    )
    original = NativeSchemaGraphIndex._lookup_native_paths

    def observed() -> tuple[object, int]:
        count = 0

        def spy(self, *args, **kwargs):
            nonlocal count
            if kwargs.get("_fork_arm_internal") is True:
                count += 1
            return original(self, *args, **kwargs)

        with patch.object(NativeSchemaGraphIndex, "_lookup_native_paths", spy):
            result = index.lookup_shared_root_forks(
                router, ALIASES[0], group=GROUP, principal=ACTOR,
            )
        return result, count

    monkeypatch.setattr(native_fork_index, "MAX_FORK_PREFORK_TARGETS", 0)
    baseline, baseline_calls = observed()
    monkeypatch.setattr(native_fork_index, "MAX_FORK_PREFORK_TARGETS", 128)
    prefork, prefork_calls = observed()
    assert prefork == baseline
    assert prefork.status == "over_k_unranked"
    assert prefork.qualified_fork_count == extra + 1
    assert prefork.candidates == ()
    assert prefork.executable_authority is False
    assert prefork.independent_quality_evidence is False
    assert baseline_calls == unsharded_calls
    assert prefork_calls == sharded_calls

    # A live callback must STILL run for every checked shard. Scheduling
    # uses only indexed structure; current availability is never cached,
    # skipped, or inferred from the structural partition.
    router.planner.availability_predicate = (
        lambda tool, _ep: not tool.key.startswith("prefork_extra_status_")
    )
    changed, changed_calls = observed()
    assert changed.status == "complete"
    assert changed.qualified_fork_count == 1
    assert len(changed.candidates) == 1
    assert changed_calls == sharded_calls
    for alias in ALIASES:
        assert index.lookup_shared_root_forks(
            router, alias, group=GROUP, principal=ACTOR,
        ) == changed


def test_prefork_admissibility_upper_bound_falls_back_to_original_path(
    monkeypatch: pytest.MonkeyPatch,
):
    """Unverified indexed noise must not consume a tiny private budget."""
    router = build_fixture(500)
    for i in range(64):
        router.add_tool(_decoy_leaf(
            f"prefork_unreviewed_status_{i}",
            "crm.fork_status", "status",
            license="unreviewed-synthetic",
        ))
    index = NativeSchemaGraphIndex.build(
        NativeSchemaPostingIndex.build(router.registry),
    )
    monkeypatch.setattr(native_fork_index, "MAX_FORK_SHARD_LOOKUPS", 2)
    result = index.lookup_shared_root_forks(
        router, ALIASES[0], group=GROUP, principal=ACTOR,
    )
    assert result.status == "complete"
    assert result.qualified_fork_count == 1
    assert len(result.candidates) == 1


@pytest.mark.parametrize("bad_mode", (None, 0, 1, "true"))
def test_dense_benchmark_requires_explicit_boolean_prefork_mode(bad_mode):
    with pytest.raises(ValueError, match="boolean prepartition"):
        benchmark_dense(
            registered_routes=500, extra_status=33,
            iterations=10, prefork=bad_mode,
        )


@pytest.mark.parametrize(
    ("extra_status", "prefork_applies"), ((127, True), (128, False)),
)
def test_prefork_exact_128_target_limit_and_129_global_probe_preserve_authority(
    monkeypatch: pytest.MonkeyPatch,
    extra_status: int,
    prefork_applies: bool,
):
    """Only native structural scheduling changes; all allowed forks stay K5.

    The baseline status leaf also counts as a source-indexed target, so
    127 extras gives *exactly* 128 eligible consumer route IDs, whereas
    128 extras gives 129 and must make an original over-cap probe first;
    subshards may still use bounded prepartition after that.
    """
    router = build_fixture(500)
    for i in range(extra_status):
        router.add_tool(_decoy_leaf(
            f"prefork_boundary_status_{i}", "crm.fork_status", "status",
        ))
    graph = NativeSchemaGraphIndex.build(
        NativeSchemaPostingIndex.build(router.registry),
    )
    original = NativeSchemaGraphIndex._lookup_native_paths

    def query_and_count(alias: str) -> tuple[object, int, str]:
        calls = 0
        first_status: str | None = None

        def counted(self, *args, **kwargs):
            nonlocal calls, first_status
            private = kwargs.get("_fork_arm_internal") is True
            if private:
                calls += 1
            result = original(self, *args, **kwargs)
            if private and first_status is None:
                first_status = result.status
            return result

        with patch.object(
            NativeSchemaGraphIndex, "_lookup_native_paths", counted,
        ):
            observed = graph.lookup_shared_root_forks(
                router, alias, group=GROUP, principal=ACTOR,
            )
        assert first_status is not None
        return observed, calls, first_status

    for alias in ALIASES:
        monkeypatch.setattr(native_fork_index, "MAX_FORK_PREFORK_TARGETS", 0)
        baseline, old_calls, old_first = query_and_count(alias)
        monkeypatch.setattr(native_fork_index, "MAX_FORK_PREFORK_TARGETS", 128)
        actual, new_calls, new_first = query_and_count(alias)
        assert actual == baseline
        assert actual.status == "over_k_unranked"
        assert actual.qualified_fork_count == extra_status + 1
        assert actual.candidates == ()
        assert actual.executable_authority is False
        assert actual.independent_quality_evidence is False
        assert old_first == "over_k_unranked"
        assert (new_first != "over_k_unranked") is prefork_applies
        assert new_calls < old_calls

    # Test against the same pinned index after current health changes.
    # Preserve authorization and never reintroduce any revoked identity.
    router.planner.availability_predicate = (
        lambda tool, _ep: not tool.key.startswith(
            "prefork_boundary_status_"
        )
    )
    for alias in ALIASES:
        monkeypatch.setattr(native_fork_index, "MAX_FORK_PREFORK_TARGETS", 0)
        baseline, _, _ = query_and_count(alias)
        monkeypatch.setattr(native_fork_index, "MAX_FORK_PREFORK_TARGETS", 128)
        actual, _, _ = query_and_count(alias)
        assert actual == baseline
        assert actual.status == "complete"
        assert actual.qualified_fork_count == 1
        assert tuple(
            (c.root_route_id, *c.branch_route_ids)
            for c in actual.candidates
        ) == (("fork_origin.read", "fork_status.read", "fork_owner.read"),)
