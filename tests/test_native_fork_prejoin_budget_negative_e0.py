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
    build_fixture,
    exhaustive_source_fork_reference,
)


@pytest.mark.parametrize(
    ("noise_count", "expected_status"),
    ((6, "complete"), (32, "over_k_unranked")),
)
def test_fork_composes_before_k_without_exceeding_private_arm_cap(
    noise_count, expected_status,
):
    """One genuine fork survives unrelated arms up to the private bound.

    More than 32 source-authorized arm paths still fail closed without
    any pretense of no-fit or an unbounded scan/ranking guarantee.
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

    for query in ALIASES:
        observed = index.lookup_shared_root_forks(
            router, query, group=GROUP, principal=ACTOR,
        )
        assert observed.status == expected_status
        assert observed.qualified_fork_count == (1 if noise_count == 6 else 0)
        if noise_count == 6:
            assert tuple(
                (c.root_route_id, *c.branch_route_ids)
                for c in observed.candidates
            ) == original
        else:
            assert observed.candidates == ()
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
