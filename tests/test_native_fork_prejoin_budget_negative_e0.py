"""#1560 E0: verify fork composition before K5, with a bounded cap."""
from __future__ import annotations

import pytest

from schemarouter import (
    EndpointSpec,
    FieldSpec,
    NativeDeclaredFieldGroup,
    ParameterSpec,
    ToolSpec,
)
from schemarouter.native_graph_index import NativeSchemaGraphIndex
from schemarouter.native_semantic_index import NativeSchemaPostingIndex
from scripts.benchmark_native_fork_fieldgroup_e0 import (
    ACTOR,
    ALIASES,
    GROUP,
    _decoy_leaf,
    build_fixture,
    exhaustive_source_fork_reference,
)


@pytest.mark.parametrize(
    ("noise_count", "expected_status"),
    ((6, "complete"), (32, "complete"), (64, "complete")),
)
def test_indexed_common_root_prefilter_elides_unrelated_arms_before_cap(
    noise_count, expected_status,
):
    """6, 32 or 64 unrelated source-typed paths do not consume fork budget.

    Same snapshot, authorized original source, and private K32 still apply
    after exact structural shared-root filtering (not from benchmark gold).
    """
    router = build_fixture(500)
    router.add_tool(ToolSpec(
        name="fork_noise_origin", source_type="crm",
        license="host-reviewed-synthetic",
        endpoints=[EndpointSpec(
            name="read", read_only=True,
            output_fields=[FieldSpec(
                name="customer_id", semantic_id="crm.noise_customer_id",
                json_schema={"type": "string"}, identifier=True,
            )],
            output_schema={
                "type": "object",
                "properties": {"customer_id": {"type": "string"}},
                "required": ["customer_id"],
            },
        )],
    ))
    for i in range(noise_count):
        router.add_tool(ToolSpec(
            name=f"fork_noise_status_{i}", source_type="crm",
            license="host-reviewed-synthetic",
            endpoints=[EndpointSpec(
                name="read", read_only=True,
                parameters=[ParameterSpec(
                    name="customer_id", semantic_id="crm.noise_customer_id",
                    required=True, json_schema={"type": "string"},
                )],
                input_schema={
                    "type": "object",
                    "properties": {"customer_id": {"type": "string"}},
                    "required": ["customer_id"],
                },
                output_fields=[FieldSpec(
                    name="status", semantic_id="crm.fork_status",
                    json_schema={"type": "string"},
                )],
            )],
        ))

    original = exhaustive_source_fork_reference(router)
    assert original == (
        ("fork_origin.read", "fork_status.read", "fork_owner.read"),
    )
    index = NativeSchemaGraphIndex.build(
        NativeSchemaPostingIndex.build(router.registry),
    )
    status_only = NativeDeclaredFieldGroup(
        aliases=ALIASES, required_fields=(GROUP.required_fields[0],),
        source_type=GROUP.source_type, license=GROUP.license,
    )
    ordinary = index.lookup(
        router, ALIASES[0], group=status_only, principal=ACTOR,
    )
    assert ordinary.status == "over_k_unranked"
    assert ordinary.candidates == ()  # Ordinary public G5 is still strict K5.
    # The internal fork-arm collector must not be callable via the public
    # strict-K API, even if a caller passes its former keyword explicitly.
    with pytest.raises(TypeError, match="unexpected keyword argument"):
        index.lookup(
            router, ALIASES[0], group=status_only, principal=ACTOR,
            _fork_arm_internal=True,
        )

    for query in ALIASES:
        observed = index.lookup_shared_root_forks(
            router, query, group=GROUP, principal=ACTOR,
        )
        assert observed.status == expected_status
        assert observed.qualified_fork_count == 1
        assert tuple(
            (c.root_route_id, *c.branch_route_ids)
            for c in observed.candidates
        ) == original
        assert observed.executable_authority is False
        assert observed.independent_quality_evidence is False

    # Remove unrelated routes only at live availability, with the same index.
    # The authorized, source-pinned genuine fork becomes discoverable again.
    router.planner.availability_predicate = (
        lambda tool, _ep: not tool.key.startswith("fork_noise_")
    )
    restored = index.lookup_shared_root_forks(
        router, ALIASES[0], group=GROUP, principal=ACTOR,
    )
    assert restored.status == "complete"
    assert restored.qualified_fork_count == 1
    assert tuple(
        (c.root_route_id, *c.branch_route_ids) for c in restored.candidates
    ) == original


def test_more_than_five_genuine_complete_forks_still_abstain_without_leak():
    """Shared-root structural filtering must not silently rank >K5 forks."""
    router = build_fixture(500)
    for i in range(5):
        router.add_tool(_decoy_leaf(
            f"fork_extra_status_{i}", "crm.fork_status", "status",
        ))
    source_forks = exhaustive_source_fork_reference(router)
    assert len(source_forks) == 6
    index = NativeSchemaGraphIndex.build(
        NativeSchemaPostingIndex.build(router.registry),
    )
    for query in ALIASES:
        result = index.lookup_shared_root_forks(
            router, query, group=GROUP, principal=ACTOR,
        )
        assert result.status == "over_k_unranked"
        assert result.qualified_fork_count == 6
        assert result.candidates == ()
        assert result.executable_authority is False
        assert result.independent_quality_evidence is False

@pytest.mark.parametrize("noise_root_count", (33, 64))
def test_dense_structural_common_roots_recheck_and_join_in_bounded_shards(
    noise_root_count,
):
    """Many plausible same-root paths must not hide one authorized fork.

    Each decoy has an approved status consumer and a *structurally* matching
    owner consumer with the WRONG license. The owner arm is unqualified even
    though the canonical graph includes its root. More than 32 authorized
    status arms survive structural prefilter; chunk by disjoint typed roots
    rather than globally abstaining before the actual source-proven join.
    """
    router = build_fixture(500)
    for i in range(noise_root_count):
        identity = f"crm.shard_customer_id_{i}"
        router.add_tool(ToolSpec(
            name=f"fork_shard_root_{i}", source_type="crm",
            license="host-reviewed-synthetic",
            endpoints=[EndpointSpec(
                name="read", read_only=True,
                output_fields=[FieldSpec(
                    name="customer_id", semantic_id=identity,
                    json_schema={"type": "string"}, identifier=True,
                )],
                output_schema={
                    "type": "object",
                    "properties": {"customer_id": {"type": "string"}},
                    "required": ["customer_id"],
                },
            )],
        ))
        for suffix, semantic, licensed in (
            ("status", "crm.fork_status", "host-reviewed-synthetic"),
            ("owner", "crm.fork_owner", "unreviewed-synthetic"),
        ):
            router.add_tool(ToolSpec(
                name=f"fork_shard_{suffix}_{i}", source_type="crm",
                license=licensed,
                endpoints=[EndpointSpec(
                    name="read", read_only=True,
                    parameters=[ParameterSpec(
                        name="customer_id", semantic_id=identity,
                        json_schema={"type": "string"}, required=True,
                    )],
                    input_schema={
                        "type": "object",
                        "properties": {"customer_id": {"type": "string"}},
                        "required": ["customer_id"],
                    },
                    output_fields=[FieldSpec(
                        name=suffix, semantic_id=semantic,
                        json_schema={"type": "string"},
                    )],
                )],
            ))

    oracle = exhaustive_source_fork_reference(router)
    assert oracle == (
        ("fork_origin.read", "fork_status.read", "fork_owner.read"),
    )
    index = NativeSchemaGraphIndex.build(
        NativeSchemaPostingIndex.build(router.registry),
    )
    common_roots = (
        set(index.field_index.postings["crm.fork_status"])
        & set(index.field_index.postings["crm.fork_owner"])
    )
    # Output targets are distinct, so compute the same graph-only root
    # intersection as production; this assertion does not feed the product.
    status_roots = {
        root for route in index.field_index.postings["crm.fork_status"]
        for root in index.graph.predecessors(route)
    }
    owner_roots = {
        root for route in index.field_index.postings["crm.fork_owner"]
        for root in index.graph.predecessors(route)
    }
    assert len(status_roots & owner_roots) == noise_root_count + 1
    assert common_roots == set()
    for query in ALIASES:
        actual = index.lookup_shared_root_forks(
            router, query, group=GROUP, principal=ACTOR,
        )
        assert actual.status == "complete"
        assert actual.qualified_fork_count == 1
        assert tuple(
            (c.root_route_id, *c.branch_route_ids)
            for c in actual.candidates
        ) == oracle
        assert actual.executable_authority is False
        assert actual.independent_quality_evidence is False


def test_one_root_multiple_identifiers_more_than_32_consumers_is_joined():
    """Typed consumer shards rescue one ID join despite 33 other-ID paths.

    Root sharding alone cannot divide a single original source route. All
    noise status leaves are individually authorized but bind account_id,
    whereas the sole extra valid owner binds customer_id on that SAME root.
    The result must contain both baseline and new genuine forks, never the
    33 account-ID status mismatches.
    """
    router = build_fixture(500)
    router.add_tool(ToolSpec(
        name="fork_fanout_origin", source_type="crm",
        license="host-reviewed-synthetic",
        endpoints=[EndpointSpec(
            name="read", read_only=True,
            output_fields=[
                FieldSpec(
                    name="customer_id", semantic_id="crm.fanout_customer_id",
                    identifier=True, json_schema={"type": "string"},
                ),
                FieldSpec(
                    name="account_id", semantic_id="crm.fanout_account_id",
                    identifier=True, json_schema={"type": "string"},
                ),
            ],
            output_schema={
                "type": "object",
                "properties": {
                    "customer_id": {"type": "string"},
                    "account_id": {"type": "string"},
                },
                "required": ["customer_id", "account_id"],
            },
        )],
    ))

    def leaf(name, semantic, input_name, input_semantic):
        return ToolSpec(
            name=name, source_type="crm", license="host-reviewed-synthetic",
            endpoints=[EndpointSpec(
                name="read", read_only=True,
                parameters=[ParameterSpec(
                    name=input_name, required=True,
                    semantic_id=input_semantic,
                    json_schema={"type": "string"},
                )],
                input_schema={
                    "type": "object",
                    "properties": {input_name: {"type": "string"}},
                    "required": [input_name],
                },
                output_fields=[FieldSpec(
                    name="value", semantic_id=semantic,
                    json_schema={"type": "string"},
                )],
            )],
        )

    customer_sem = "crm.fanout_customer_id"
    account_sem = "crm.fanout_account_id"
    router.add_tool(leaf(
        "fork_fanout_status", "crm.fork_status", "customer_id",
        customer_sem,
    ))
    router.add_tool(leaf(
        "fork_fanout_owner", "crm.fork_owner", "customer_id",
        customer_sem,
    ))
    for i in range(33):
        router.add_tool(leaf(
            f"fork_fanout_noise_status_{i}",
            "crm.fork_status", "account_id", account_sem,
        ))

    # Deliberately source-constructed expected identities; test never
    # supplies this positive control to production retrieval.
    expected = (
        ("fork_fanout_origin.read",
         "fork_fanout_status.read", "fork_fanout_owner.read"),
        ("fork_origin.read",
         "fork_status.read", "fork_owner.read"),
    )
    index = NativeSchemaGraphIndex.build(
        NativeSchemaPostingIndex.build(router.registry),
    )
    assert len(index.graph.predecessors("fork_fanout_owner.read")) == 1
    assert all(
        "fork_fanout_origin.read" in index.graph.predecessors(
            f"fork_fanout_noise_status_{i}.read"
        ) for i in range(33)
    )
    for query in ALIASES:
        result = index.lookup_shared_root_forks(
            router, query, group=GROUP, principal=ACTOR,
        )
        assert result.status == "complete"
        assert result.qualified_fork_count == 2
        assert tuple(
            (c.root_route_id, *c.branch_route_ids) for c in result.candidates
        ) == expected
        assert result.executable_authority is False
        assert result.independent_quality_evidence is False


def test_same_root_sharding_preserves_public_k5_and_budget_abstention(
    monkeypatch: pytest.MonkeyPatch,
):
    """No shard may promote >5 genuinely complete forks or leak partial arms.

    The same original customer-ID root connects 33 extra approved status
    consumers and one approved owner consumer. All 34 forks are complete;
    even with internal target sharding this remains unranked >K5. Force a
    *smaller test-only internal attempt budget* to prove exhaustion returns
    only a no-disclosure abstention, never the partially visited shards.
    Live health removal must restore the sole original fork on the SAME
    version-pinned index.
    """
    router = build_fixture(500)
    for i in range(33):
        router.add_tool(_decoy_leaf(
            f"fork_extra_status_{i}", "crm.fork_status", "status",
        ))
    index = NativeSchemaGraphIndex.build(
        NativeSchemaPostingIndex.build(router.registry),
    )
    oracle = exhaustive_source_fork_reference(router)
    assert len(oracle) == 34
    assert all(root == "fork_origin.read" for root, _, _ in oracle)
    # The generic source oracle is intentionally not used to select routes
    # or control the query. Only exact permitted constructed source contracts
    # and observed status/count are inspected.
    for query in ALIASES:
        result = index.lookup_shared_root_forks(
            router, query, group=GROUP, principal=ACTOR,
        )
        assert result.status == "over_k_unranked"
        assert result.qualified_fork_count == 34
        assert result.candidates == ()
        assert result.executable_authority is False
        assert result.independent_quality_evidence is False

    # The production constant is 64. Tightening it for an E0 negative
    # forces one-target-root recursion to exhaust before all shards.
    monkeypatch.setattr(
        "schemarouter.native_fork_index.MAX_FORK_SHARD_LOOKUPS", 2,
    )
    for query in ALIASES:
        exhausted = index.lookup_shared_root_forks(
            router, query, group=GROUP, principal=ACTOR,
        )
        assert exhausted.status == "over_k_unranked"
        assert exhausted.qualified_fork_count == 0
        assert exhausted.candidates == ()
        assert exhausted.executable_authority is False
        assert exhausted.independent_quality_evidence is False

    # Even the tightened budget must handle a live availability revocation
    # without a catalog rebuild or stale partial-candidate disclosure.
    router.planner.availability_predicate = (
        lambda tool, _ep: not tool.key.startswith("fork_extra_status_")
    )
    restored = index.lookup_shared_root_forks(
        router, ALIASES[0], group=GROUP, principal=ACTOR,
    )
    assert restored.status == "complete"
    assert restored.qualified_fork_count == 1
    assert tuple(
        (c.root_route_id, *c.branch_route_ids)
        for c in restored.candidates
    ) == (("fork_origin.read", "fork_status.read", "fork_owner.read"),)
