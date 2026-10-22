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
