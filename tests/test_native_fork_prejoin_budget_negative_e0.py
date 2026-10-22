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
