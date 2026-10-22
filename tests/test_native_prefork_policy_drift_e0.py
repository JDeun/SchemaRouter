"""Developer E0: reject source-native dense fork if host policy mutates midquery."""
from __future__ import annotations

import pytest

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    DataScopeRule,
    native_fork_index,
)
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


@pytest.mark.parametrize("extra", (33, 64))
@pytest.mark.parametrize("optimized", (False, True))
@pytest.mark.parametrize("policy_change", ("deny_owner", "hide_extra"))
def test_current_policy_changes_during_original_fork_query_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
    extra: int,
    optimized: bool,
    policy_change: str,
) -> None:
    """Original-current policy snapshot must outlive source health callbacks."""
    router = build_fixture(500)
    for i in range(extra):
        router.add_tool(_decoy_leaf(
            f"midpolicy_status_{i}", "crm.fork_status", "status",
        ))
    graph = NativeSchemaGraphIndex.build(
        NativeSchemaPostingIndex.build(router.registry),
    )
    original_policy = router.authorization_policy
    assert original_policy is not None
    monkeypatch.setattr(
        native_fork_index,
        "MAX_FORK_PREFORK_TARGETS",
        128 if optimized else 0,
    )
    mutations = 0

    def live_health(tool, _endpoint):
        nonlocal mutations
        if tool.key == "fork_origin" and mutations == 0:
            mutations += 1
            deny_rules = (
                (AuthorizationRule(
                    effect="deny", operation="fork_owner.read",
                    roles_any=("reader",),
                ),) if policy_change == "deny_owner" else ()
            )
            hidden_rules = (
                (DataScopeRule(
                    operation="midpolicy_status_*.read",
                    roles_any=("reader",), hidden_fields=("status",),
                ),) if policy_change == "hide_extra" else ()
            )
            router.authorization_policy = AuthorizationPolicy(
                default_effect="deny",
                rules=deny_rules + (AuthorizationRule(
                    effect="allow", operation="*.read", roles_any=("reader",),
                ),),
                data_rules=hidden_rules,
            )
        return True

    router.planner.availability_predicate = live_health
    with pytest.raises(PolicyViolationError):
        graph.lookup_shared_root_forks(
            router, ALIASES[0], group=GROUP, principal=ACTOR,
        )
    assert mutations == 1

    # The SAME pinned original source index must not cache revoked policy.
    router.authorization_policy = original_policy
    router.planner.availability_predicate = lambda _tool, _endpoint: True
    for alias in ALIASES:
        restored = graph.lookup_shared_root_forks(
            router, alias, group=GROUP, principal=ACTOR,
        )
        assert restored.status == "over_k_unranked"
        assert restored.qualified_fork_count == extra + 1
        assert restored.candidates == ()
        assert restored.executable_authority is False
        assert restored.independent_quality_evidence is False
