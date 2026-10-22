"""#1700 E0: dense prefork cannot disclose health-drifted source evidence."""
from __future__ import annotations

import pytest

from schemarouter import native_fork_index
from schemarouter.errors import PolicyViolationError
from schemarouter.native_graph_index import NativeSchemaGraphIndex
from schemarouter.native_semantic_index import NativeSchemaPostingIndex
from scripts.benchmark_native_fork_fieldgroup_e0 import (
    ACTOR,
    ALIASES,
    GROUP,
    _decoy_leaf,
    build_fixture,
)

PRIVATE_CALLBACK_DETAIL = "HOST_INTERNAL_SECRET_MUST_NOT_LEAK"


@pytest.mark.parametrize("extra_status", (33, 64))
@pytest.mark.parametrize("optimized", (False, True))
@pytest.mark.parametrize("failure", ("revoked_during_scan", "provider_exception"))
def test_dense_prefork_midscan_health_failure_is_sanitized_and_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
    extra_status: int,
    optimized: bool,
    failure: str,
):
    """Use real native typed graph plus volatile host-owned current health.

    Source route fingerprint and authorization policies remain pinned; the
    original callback alone mutates. A route that was eligible when first
    read becomes unavailable during the same private candidate validation,
    or its provider-owned health callback throws. Neither the optimized
    nor the baseline private collector may emit a partial answer.
    """
    router = build_fixture(500)
    for i in range(extra_status):
        router.add_tool(_decoy_leaf(
            f"prefork_volatile_status_{i}", "crm.fork_status", "status",
        ))
    index = NativeSchemaGraphIndex.build(
        NativeSchemaPostingIndex.build(router.registry),
    )
    monkeypatch.setattr(
        native_fork_index, "MAX_FORK_PREFORK_TARGETS",
        128 if optimized else 0,
    )
    volatile_calls = 0

    def live_health(tool, _endpoint):
        nonlocal volatile_calls
        if tool.key != "prefork_volatile_status_0":
            return True
        volatile_calls += 1
        if failure == "provider_exception":
            raise RuntimeError(PRIVATE_CALLBACK_DETAIL)
        return volatile_calls == 1

    router.planner.availability_predicate = live_health
    with pytest.raises(
        PolicyViolationError, match="G5 fork eligibility changed during lookup",
    ) as rejected:
        index.lookup_shared_root_forks(
            router, ALIASES[0], group=GROUP, principal=ACTOR,
        )
    assert PRIVATE_CALLBACK_DETAIL not in str(rejected.value)
    assert volatile_calls >= (2 if failure == "revoked_during_scan" else 1)


@pytest.mark.parametrize("extra_status", (33, 64))
def test_dense_prefork_stable_current_health_matches_strict_k5(
    extra_status: int,
):
    """A stable current health callback is still inspected on every shard."""
    router = build_fixture(500)
    for i in range(extra_status):
        router.add_tool(_decoy_leaf(
            f"prefork_stable_status_{i}", "crm.fork_status", "status",
        ))
    index = NativeSchemaGraphIndex.build(
        NativeSchemaPostingIndex.build(router.registry),
    )
    seen = 0

    def live_health(tool, _endpoint):
        nonlocal seen
        if tool.key.startswith("prefork_stable_status_"):
            seen += 1
        return True

    router.planner.availability_predicate = live_health
    for alias in ALIASES:
        result = index.lookup_shared_root_forks(
            router, alias, group=GROUP, principal=ACTOR,
        )
        assert result.status == "over_k_unranked"
        assert result.qualified_fork_count == extra_status + 1
        assert result.candidates == ()
        assert result.executable_authority is False
    assert seen >= extra_status
