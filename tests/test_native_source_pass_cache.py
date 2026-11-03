"""E0 bounded source-shape diagnostics; no latency/SLO or independent E2 claim."""
from __future__ import annotations

import cProfile
import pstats
from types import MethodType

import pytest

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    DataScopeRule,
    InMemoryRegistry,
    PolicyViolationError,
    RegistryExecutor,
    SchemaPlanner,
    SchemaRouter,
    ToolSpec,
)
from schemarouter.field_group_retrieval import _complete_fields
from schemarouter.native_graph_index import NativeSchemaGraphIndex
from schemarouter.native_semantic_index import NativeSchemaPostingIndex
from scripts import benchmark_native_g5_build_fingerprint_ab_e0 as fixture


def _router(monkeypatch, n: int, packed: bool = True, *, registry=None):
    monkeypatch.setattr(fixture, "TOOLS", 2)
    monkeypatch.setattr(fixture, "ENDPOINTS_PER_TOOL", 1)
    templates = fixture._synthetic_router().registry.tools()
    root, consumer = (tool.endpoints[0] for tool in templates)
    endpoints = [root.model_copy(update={"name": "root"}, deep=True)] + [
        consumer.model_copy(update={"name": f"read_{i}"}, deep=True) for i in range(1, n)
    ]
    router = SchemaRouter(registry=registry, authorization_policy=AuthorizationPolicy(
        default_effect="deny", rules=(AuthorizationRule(
            effect="allow", operation="*.*", roles_any=("reader",),
        ),),
    ))
    groups = [endpoints] if packed else [[endpoint] for endpoint in endpoints]
    for i, group in enumerate(groups):
        router.add_tool(ToolSpec(name=f"tool_{i}", source_type="crm",
                                 license="synthetic-reviewed", endpoints=group))
    posting = NativeSchemaPostingIndex.build(router.registry)
    graph = NativeSchemaGraphIndex.build(posting)
    return router, posting, graph


def _lookup(index, router):
    return index.lookup(router, fixture.QUERY, group=fixture.GROUP, principal=fixture.PRINCIPAL)


def _profile(index, router):
    profiler = cProfile.Profile()
    result = profiler.runcall(_lookup, index, router)
    stats = pstats.Stats(profiler).stats

    def calls(function):
        code = function.__code__
        return stats.get((code.co_filename, code.co_firstlineno, code.co_name), (0, 0))[1]

    return result, calls(InMemoryRegistry.get), calls(ToolSpec.fingerprint.fget)


@pytest.mark.parametrize("n", (4, 100, 500))
@pytest.mark.parametrize("packed", (False, True))
@pytest.mark.parametrize("kind", ("posting", "graph"))
def test_original_source_oracle_parity_with_linear_source_copy_and_hash_counts(
    monkeypatch, n: int, packed: bool, kind: str,
) -> None:
    router, posting, graph = _router(monkeypatch, n, packed)
    # Independent original source scan, outside the profiled lookup.
    expected = {
        f"{tool.key}.{endpoint.name}"
        for tool in router.registry.tools() for endpoint in tool.endpoints
        if _complete_fields(endpoint.output_fields, fixture.GROUP.required_fields)
    }
    assert set(posting.postings["crm.status"]) == expected
    assert len(expected) == n - 1
    result, reads, hashes = _profile(posting if kind == "posting" else graph, router)
    count = result.qualified_count if kind == "posting" else result.qualified_path_count
    assert count == len(expected)
    if n > 5:
        assert result.status == "over_k_unranked" and result.candidates == ()
    else:
        actual = {
            candidate.route_id if kind == "posting" else candidate.consumer_route_id
            for candidate in result.candidates
        }
        assert result.status == "complete" and actual == expected
    expected_reads = 2 if packed else 2 * (n - 1 if kind == "posting" else n)
    assert reads == hashes == expected_reads, "Each pass must freshly verify every used tool"


@pytest.mark.parametrize("kind", ("posting", "graph"))
@pytest.mark.parametrize("custom", (
    "availability", "scope", "authorization", "policy", "rule", "registry", "registry_get", "audit",
    "scope_class", "authorization_class", "policy_class", "rule_class", "registry_class",
    "health_class", "planner_class", "executor_class",
))
def test_user_callbacks_keep_fresh_detached_source_snapshots(monkeypatch, kind: str, custom: str):
    class CustomRegistry(InMemoryRegistry):
        pass

    router, posting, graph = _router(
        monkeypatch, 8, registry=CustomRegistry() if custom == "registry" else None,
    )
    seen = []

    def observe(tool):
        assert "probe" not in tool.metadata, "An earlier callback contaminated source evidence"
        tool.metadata["probe"] = True
        seen.append(tool)

    if custom == "availability":
        def health(tool, endpoint):
            observe(tool)
            return True
        router.planner.availability_predicate = health
    elif custom in {"scope", "scope_class"}:
        original = router._data_scope_endpoint_view

        def scope(_router, actor, tool, endpoint):
            observe(tool)
            return original(actor, tool, endpoint)
        if custom == "scope":
            router._data_scope_endpoint_view = MethodType(scope, router)
        else:
            monkeypatch.setattr(SchemaRouter, "_data_scope_endpoint_view", scope)
    elif custom in {"authorization", "authorization_class"}:
        original = router._authorization_predicate

        def authorization(_router, actor):
            permitted = original(actor)

            def allowed(tool, endpoint):
                observe(tool)
                return permitted(tool, endpoint)
            return allowed
        if custom == "authorization":
            router._authorization_predicate = MethodType(authorization, router)
        else:
            monkeypatch.setattr(SchemaRouter, "_authorization_predicate", authorization)
    elif custom == "policy":
        class CustomPolicy(AuthorizationPolicy):
            def visible(self, actor, tool, endpoint):
                observe(tool)
                return super().visible(actor, tool, endpoint)
        router.authorization_policy = CustomPolicy(rules=router.authorization_policy.rules)
    elif custom == "policy_class":
        original = AuthorizationPolicy.visible

        def visible(policy, actor, tool, endpoint):
            observe(tool)
            return original(policy, actor, tool, endpoint)
        monkeypatch.setattr(AuthorizationPolicy, "visible", visible)
    elif custom == "rule":
        rule = router.authorization_policy.rules[0]
        original = rule.matches

        def matches(_rule, actor, tool, endpoint, call=None):
            observe(tool)
            return original(actor, tool, endpoint, call)
        object.__setattr__(rule, "matches", MethodType(matches, rule))
    elif custom == "rule_class":
        original = AuthorizationRule.matches

        def matches(rule, actor, tool, endpoint, call=None):
            observe(tool)
            return original(rule, actor, tool, endpoint, call)
        monkeypatch.setattr(AuthorizationRule, "matches", matches)
    elif custom == "registry_get":
        original = router.registry.get

        def get(_registry, key):
            tool = original(key)
            observe(tool)
            return tool
        router.registry.get = MethodType(get, router.registry)
    elif custom == "registry_class":
        original = InMemoryRegistry.get

        def get(registry, key):
            tool = original(registry, key)
            observe(tool)
            return tool
        monkeypatch.setattr(InMemoryRegistry, "get", get)
    elif custom == "health_class":
        original = SchemaRouter._is_snapshot_access_available

        def health(_router, tool, endpoint):
            observe(tool)
            return original(_router, tool, endpoint)
        monkeypatch.setattr(SchemaRouter, "_is_snapshot_access_available", health)
        router.planner.availability_predicate = router._is_snapshot_access_available
    elif custom == "planner_class":
        original = SchemaPlanner._snapshot_tool_fingerprint

        def fingerprint(planner, tool):
            observe(tool)
            return original(planner, tool)
        monkeypatch.setattr(SchemaPlanner, "_snapshot_tool_fingerprint", fingerprint)
        for i in range(1, 8):
            router.mark_access_unavailable("tool_0", f"read_{i}", cooldown_seconds=0)
    elif custom == "executor_class":
        original = RegistryExecutor.is_access_available_for_contract_lazy

        def available(executor, *args):
            return original(executor, *args)
        monkeypatch.setattr(RegistryExecutor, "is_access_available_for_contract_lazy", available)
    elif custom == "registry":
        pass
    else:
        router.authorization_audit_hook = lambda event: None

    result, reads, _hashes = _profile(posting if kind == "posting" else graph, router)
    assert result.status == "over_k_unranked" and result.candidates == ()
    assert reads == (14 if kind == "posting" else 28)
    assert len({id(tool) for tool in seen}) == len(seen)
    assert "probe" not in router.registry.tools()[0].metadata


@pytest.mark.parametrize("kind", ("posting", "graph"))
@pytest.mark.parametrize("change", ("health", "policy", "scope", "registry", "registry_identity"))
def test_same_callback_revocation_never_publishes_cached_candidates(
    monkeypatch, kind: str, change: str,
) -> None:
    router, posting, graph = _router(monkeypatch, 8)
    revoked = False
    policy = router.authorization_policy

    def health(tool, endpoint):
        nonlocal revoked
        if endpoint.name == "read_7" and not revoked:
            revoked = True
            if change == "policy":
                object.__setattr__(policy, "rules", ())
            elif change == "scope":
                object.__setattr__(policy, "data_rules", (
                    DataScopeRule(hidden_fields=("status",)),
                ))
            elif change == "registry":
                replacement = tool.model_copy(update={"description": "changed source"}, deep=True)
                router.registry.register(replacement, replace=True)
            elif change == "registry_identity":
                registry = InMemoryRegistry()
                for source in router.registry.tools():
                    registry.register(source)
                router.registry = registry
        return not (change == "health" and revoked and endpoint.name == "read_1")

    router.planner.availability_predicate = health
    with pytest.raises(PolicyViolationError):
        _lookup(posting if kind == "posting" else graph, router)
    assert revoked


@pytest.mark.parametrize("kind", ("posting", "graph"))
def test_default_health_revocation_during_ranker_is_rechecked_before_publication(monkeypatch, kind):
    router, posting, graph = _router(monkeypatch, 7)
    calls = 0

    def ranker(query, candidates, k):
        nonlocal calls
        calls += 1
        router.mark_access_unavailable("tool_0", "read_1", cooldown_seconds=120)
        return tuple(range(k))

    with pytest.raises(PolicyViolationError):
        (posting if kind == "posting" else graph).lookup(
            router, fixture.QUERY, group=fixture.GROUP, principal=fixture.PRINCIPAL,
            _research_ranker=ranker,
        )
    assert calls == 1


@pytest.mark.parametrize("kind", ("posting", "graph"))
def test_default_cooldowns_reuse_source_hash_but_still_deny_and_recover(monkeypatch, kind):
    router, posting, graph = _router(monkeypatch, 8)
    for i in range(1, 8):
        router.mark_access_unavailable("tool_0", f"read_{i}", cooldown_seconds=120)
    index = posting if kind == "posting" else graph
    result, reads, hashes = _profile(index, router)
    assert result.status == "no_proven_hit" and result.candidates == ()
    assert reads == hashes == 1
    router.mark_access_available("tool_0", "read_7")
    result, reads, hashes = _profile(index, router)
    assert result.status == "complete" and len(result.candidates) == 1
    assert reads == hashes == 2
