"""#1560 E0: document pre-join K5 false refusal on a source-valid fork."""
from __future__ import annotations

from schemarouter import EndpointSpec, FieldSpec, ParameterSpec, ToolSpec
from schemarouter.native_graph_index import NativeSchemaGraphIndex
from schemarouter.native_semantic_index import NativeSchemaPostingIndex
from scripts.benchmark_native_fork_fieldgroup_e0 import (
    ACTOR,
    ALIASES,
    GROUP,
    build_fixture,
    exhaustive_source_fork_reference,
)


def test_one_valid_fork_abstains_when_unrelated_left_arm_exceeds_k():
    """Known negative: a positive source oracle with a pre-join overflow.

    Six unrelated status consumers bind another source-native identifier.
    The owner leaf only binds the genuine root. There is exactly one
    legitimate joined fork, but the left single-field K5 gate abstains
    before the shared-root intersection. This is NOT a successful Recall@5.
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
    for i in range(6):
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
    for query in ALIASES:
        observed = index.lookup_shared_root_forks(
            router, query, group=GROUP, principal=ACTOR,
        )
        # Explicitly record a known false refusal, not a privacy/quality pass.
        assert observed.status == "over_k_unranked"
        assert observed.qualified_fork_count == 0
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
