"""Independent-from-prefilter exhaustive comparison, using the same canonical G5.

The prefilter-off view evaluates every native semantic posting before typed
checks; the optimized view must preserve the EXACT same scoped result.
This is adversarial synthetic consistency, not external publisher gold.
"""
from __future__ import annotations

from dataclasses import replace
from random import Random

import pytest

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    DataScopeRule,
    EndpointSpec,
    FieldSpec,
    ParameterSpec,
    ToolSpec,
)
from schemarouter.native_graph_index import NativeSchemaGraphIndex
from schemarouter.native_semantic_index import NativeSchemaPostingIndex
from scripts.benchmark_indexed_g5_selectivity_e0 import (
    BROAD_GROUP,
    BROAD_QUERY,
)
from scripts.benchmark_indexed_native_graph_g5_cpu_e0 import (
    GROUP,
    PRINCIPAL,
    QUERY,
    _synthetic_router,
)


def _fixture():
    router = _synthetic_router(64)
    for i in range(7):
        router.add_tool(ToolSpec(
            name=f"consumer_{i}", source_type="crm",
            license="host-reviewed-synthetic",
            endpoints=[EndpointSpec(
                name="read", read_only=True,
                parameters=[ParameterSpec(
                    name="customer_id", required=True, location="argument",
                    semantic_id="crm.customer_id",
                    json_schema={"type": "string"},
                )],
                input_schema={
                    "type": "object",
                    "properties": {"customer_id": {"type": "string"}},
                    "required": ["customer_id"],
                },
                output_fields=[FieldSpec(
                    name="status", semantic_id="crm.status",
                    json_schema={"type": "string"},
                )],
            )],
        ))
    idx = NativeSchemaGraphIndex.build(
        NativeSchemaPostingIndex.build(router.registry),
    )
    exhaustive = replace(
        idx, edge_consumer_routes=frozenset(idx.field_index.route_locations),
    )
    assert exhaustive.graph is idx.graph
    assert exhaustive.field_index is idx.field_index
    return router, idx, exhaustive


def _assert_same(router, optimized, exhaustive, *, query=QUERY, group=GROUP):
    expected = exhaustive.lookup(
        router, query, principal=PRINCIPAL, group=group,
    )
    actual = optimized.lookup(
        router, query, principal=PRINCIPAL, group=group,
    )
    assert actual == expected
    assert actual.requested_k == 5
    assert actual.executable_authority is False
    assert actual.calibrated_no_fit is False
    assert actual.independent_quality_evidence is False
    if actual.status == "over_k_unranked":
        assert actual.qualified_path_count > 5
        assert not actual.candidates


@pytest.mark.parametrize("seed", [1, 7, 17, 42, 20261019])
def test_prefilter_equal_to_unfiltered_graph_for_randomized_authority(seed):
    router, fast, exhaustive = _fixture()
    rand = Random(seed)
    for _ in range(15):
        allowed = tuple(
            name for name in (
                "case_service", *(f"consumer_{i}" for i in range(7))
            )
            if rand.choice((True, False))
        )
        root_allowed = rand.choice((True, False))
        hidden = rand.choice((True, False))
        unavailable = frozenset(
            name for name in ("contact_directory", *allowed)
            if rand.randrange(4) == 0
        )
        names = ((*allowed, "contact_directory") if root_allowed else allowed)
        router.authorization_policy = AuthorizationPolicy(
            default_effect="deny",
            rules=tuple(AuthorizationRule(
                effect="allow", operation=f"{name}.read",
                roles_any=("reader",),
            ) for name in names),
            data_rules=(DataScopeRule(
                operation="contact_directory.read",
                roles_any=("reader",), hidden_fields=("customer_id",),
            ),) if hidden else (),
        )
        router.planner.availability_predicate = (
            lambda tool, ep, blocked=unavailable: tool.key not in blocked
        )
        _assert_same(router, fast, exhaustive)
        _assert_same(
            router, fast, exhaustive,
            query=BROAD_QUERY, group=BROAD_GROUP,
        )


def test_exact_k_boundary_and_rejection_match_unfiltered_graph():
    router, fast, exhaustive = _fixture()
    all_consumers = ("case_service", *(f"consumer_{i}" for i in range(7)))
    for limit in (0, 1, 5, 6, 8):
        router.authorization_policy = AuthorizationPolicy(
            default_effect="deny",
            rules=tuple(AuthorizationRule(
                effect="allow", operation=f"{name}.read",
                roles_any=("reader",),
            ) for name in ("contact_directory", *all_consumers[:limit])),
        )
        router.planner.availability_predicate = None
        _assert_same(router, fast, exhaustive)
        result = fast.lookup(
            router, QUERY, group=GROUP, principal=PRINCIPAL,
        )
        assert result.qualified_path_count == limit
        assert len(result.candidates) == (limit if limit <= 5 else 0)
