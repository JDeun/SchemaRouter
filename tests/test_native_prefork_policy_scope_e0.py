"""#1700: indexed pre-fork structural shards never override current host policy.

Developer-authored E0 source fixture. Public K5, source/authorization scope
and exact current principal must remain identical to the pre-optimization
native fork lookup. Does not exercise a publisher or external agent E2.
"""
from __future__ import annotations

import pytest

from schemarouter import AuthorizationPolicy, AuthorizationRule, DataScopeRule, native_fork_index
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
@pytest.mark.parametrize("restriction", ("deny_extra", "hide_extra", "deny_owner"))
def test_dense_original_source_prefork_enforces_updated_policy_and_scoped_fields(
    monkeypatch: pytest.MonkeyPatch, extra: int, restriction: str,
) -> None:
    """Changing current policy without a registry/index rebuild must work.

    The unscoped semantic posting and typed graph still include ALL original
    consumer paths. Only the registered current policy decides whether a
    principal can see each field, even after structural prepartitioning.
    """
    router = build_fixture(500)
    for i in range(extra):
        router.add_tool(_decoy_leaf(
            f"prefork_security_status_{i}", "crm.fork_status", "status",
        ))
    graph = NativeSchemaGraphIndex.build(
        NativeSchemaPostingIndex.build(router.registry),
    )
    saved_policy = router.authorization_policy
    assert saved_policy is not None

    def lookup(alias: str, use_prefork: bool):
        monkeypatch.setattr(
            native_fork_index, "MAX_FORK_PREFORK_TARGETS",
            128 if use_prefork else 0,
        )
        return graph.lookup_shared_root_forks(
            router, alias, group=GROUP, principal=ACTOR,
        )

    for alias in ALIASES:
        prior = lookup(alias, False)
        assert lookup(alias, True) == prior
        assert prior.status == "over_k_unranked"
        assert prior.qualified_fork_count == extra + 1
        assert prior.candidates == ()

    deny_target = (
        "fork_owner.read" if restriction == "deny_owner"
        else "prefork_security_status_*.read"
    )
    deny_rules = (
        (AuthorizationRule(
            effect="deny", operation=deny_target,
            roles_any=("reader",),
        ),) if restriction != "hide_extra" else ()
    )
    router.authorization_policy = AuthorizationPolicy(
        default_effect="deny",
        rules=deny_rules + (
            AuthorizationRule(
                effect="allow", operation="*.read", roles_any=("reader",),
            ),
        ),
        data_rules=(
            (DataScopeRule(
                operation="prefork_security_status_*.read",
                roles_any=("reader",), hidden_fields=("status",),
            ),) if restriction == "hide_extra" else ()
        ),
    )

    for alias in ALIASES:
        baseline = lookup(alias, False)
        actual = lookup(alias, True)
        assert actual == baseline
        assert actual.executable_authority is False
        assert actual.independent_quality_evidence is False
        if restriction == "deny_owner":
            assert actual.status == "no_proven_hit"
            assert actual.qualified_fork_count == 0
            assert actual.candidates == ()
        else:
            assert actual.status == "complete"
            assert actual.qualified_fork_count == 1
            assert tuple(
                (c.root_route_id, *c.branch_route_ids)
                for c in actual.candidates
            ) == ((
                "fork_origin.read", "fork_status.read",
                "fork_owner.read",
            ),)

    # The SAME pinned original graph must observe current policy restoration.
    router.authorization_policy = saved_policy
    for alias in ALIASES:
        baseline = lookup(alias, False)
        actual = lookup(alias, True)
        assert actual == baseline
        assert actual.status == "over_k_unranked"
        assert actual.qualified_fork_count == extra + 1
        assert actual.candidates == ()
