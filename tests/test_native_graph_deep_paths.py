"""#1560: exact-depth 2–4 edge G5 typed index exploration (E0)."""
from __future__ import annotations

import pytest

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    DataScopeRule,
    EndpointSpec,
    FieldSpec,
    ParameterSpec,
    PrincipalContext,
    SchemaRouter,
    ToolSpec,
)
from schemarouter.capability_contracts import CapabilityFieldContract
from schemarouter.errors import PolicyViolationError
from schemarouter.field_group_retrieval import NativeDeclaredFieldGroup
from schemarouter.native_graph_index import NativeSchemaGraphIndex
from schemarouter.native_semantic_index import NativeSchemaPostingIndex

ACTOR = PrincipalContext(subject="auditor", roles=("reader",))
ALIASES = ("payment status", "결제 상태", "支払状況")
GROUP = NativeDeclaredFieldGroup(
    aliases=ALIASES,
    required_fields=(CapabilityFieldContract(
        semantic_id="billing.status", json_schema={"type": "string"},
    ),),
    source_type="billing", license="reviewed",
)


def _tool(
    name: str,
    *,
    requires: str | None = None,
    output: str = "billing.record_id",
    output_name: str = "record_id",
    output_type: str = "string",
    input_type: str = "string",
    identifier: bool = True,
) -> ToolSpec:
    param = "from_id"
    parameters = (
        [ParameterSpec(
            name=param, semantic_id=requires,
            required=True, json_schema={"type": input_type},
        )] if requires is not None else []
    )
    return ToolSpec(
        name=name, source_type="billing", license="reviewed",
        endpoints=[EndpointSpec(
            name="read", read_only=True, parameters=parameters,
            input_schema=(
                {"type": "object",
                 "properties": {param: {"type": input_type}},
                 "required": [param]}
                if requires is not None else {}
            ),
            output_fields=[FieldSpec(
                name=output_name, semantic_id=output,
                identifier=identifier, json_schema={"type": output_type},
            )],
        )],
    )


def _router(
    hops: int, *,
    targets: int = 1,
    broken_type_at: int | None = None,
    hidden_at: int | None = None,
    denied_at: int | None = None,
    noise: int = 0,
) -> SchemaRouter:
    assert hops in (2, 3, 4)
    rules = tuple(
        AuthorizationRule(
            effect="deny", operation=f"mid_{denied_at}.read",
            roles_any=("reader",),
        ) for _ in ((),) if denied_at is not None
    ) + (AuthorizationRule(
        effect="allow", operation="*.read", roles_any=("reader",),
    ),)
    data_rules = (
        (DataScopeRule(
            operation=f"mid_{hidden_at}.read", roles_any=("reader",),
            hidden_fields=("record_id",),
        ),) if hidden_at is not None else ()
    )
    router = SchemaRouter(authorization_policy=AuthorizationPolicy(
        default_effect="deny", rules=rules, data_rules=data_rules,
    ))
    router.add_tool(_tool("root", output="billing.id_0"))
    for idx in range(hops - 1):
        router.add_tool(_tool(
            f"mid_{idx}",
            requires=f"billing.id_{idx}",
            output=f"billing.id_{idx + 1}",
            input_type="integer" if idx == broken_type_at else "string",
        ))
    for idx in range(targets):
        router.add_tool(_tool(
            f"target_{idx}",
            requires=f"billing.id_{hops - 1}",
            output="billing.status",
            output_name="status", identifier=False,
        ))
    for idx in range(noise):
        router.add_tool(_tool(
            f"unrelated_{idx}", output=f"other.noise_{idx}",
        ))
    return router


def _index(router: SchemaRouter) -> NativeSchemaGraphIndex:
    return NativeSchemaGraphIndex.build(
        NativeSchemaPostingIndex.build(router.registry),
    )


@pytest.mark.parametrize("hops", (2, 3, 4))
@pytest.mark.parametrize("query", ALIASES)
def test_bounded_original_2_to_4_edges_are_exact_and_source_pinned(hops, query):
    router = _router(hops)
    graph = _index(router)
    result = graph.lookup_bounded_paths(
        router, query, group=GROUP, principal=ACTOR, hops=hops,
    )
    expected = (
        ("root.read",)
        + tuple(f"mid_{i}.read" for i in range(hops - 1))
        + ("target_0.read",)
    )
    assert result.status == "complete"
    assert result.requested_hops == hops
    assert result.qualified_path_count == 1
    candidate, = result.candidates
    assert candidate.route_ids == expected
    assert len(candidate.parameter_bindings) == hops
    assert all(binding == (("from_id", "record_id"),)
               for binding in candidate.parameter_bindings)
    assert candidate.route_fingerprints == tuple(
        graph.field_index.route_fingerprints[route]
        for route in expected
    )
    assert candidate.target_output_fields == ("status",)
    assert candidate.source_root_parameters == ()
    assert not result.independent_quality_evidence
    assert not result.calibrated_no_fit
    assert not result.executable_authority


def test_three_hop_chain_cannot_masquerade_as_two_hop_route():
    router = _router(3)
    graph = _index(router)
    out = graph.lookup_bounded_paths(
        router, ALIASES[0], group=GROUP, principal=ACTOR, hops=2,
    )
    assert out.status == "no_proven_hit"
    assert out.candidates == ()
    assert graph.lookup_two_hop(
        router, ALIASES[0], group=GROUP, principal=ACTOR,
    ).status == "no_proven_hit"


@pytest.mark.parametrize("depth", (3, 4))
@pytest.mark.parametrize("failure", ("type", "hidden", "denied"))
def test_deep_chain_rejects_wrong_types_hidden_or_denied_middle(depth, failure):
    router = _router(
        depth,
        broken_type_at=0 if failure == "type" else None,
        hidden_at=0 if failure == "hidden" else None,
        denied_at=0 if failure == "denied" else None,
    )
    result = _index(router).lookup_bounded_paths(
        router, ALIASES[0], group=GROUP, principal=ACTOR, hops=depth,
    )
    assert result.status == "no_proven_hit"
    assert result.qualified_path_count == 0
    assert result.candidates == ()


def test_three_hop_over_k_refuses_to_expose_six_routes():
    router = _router(3, targets=6)
    result = _index(router).lookup_bounded_paths(
        router, ALIASES[0], group=GROUP, principal=ACTOR, hops=3,
    )
    assert result.status == "over_k_unranked"
    assert result.qualified_path_count == 6
    assert result.candidates == ()


def test_three_hop_query_does_not_fetch_unrelated_registered_tools(monkeypatch):
    router = _router(3, noise=300)
    graph = _index(router)
    actual_get = router.registry.get
    seen: list[str] = []

    def bounded(key):
        seen.append(key)
        assert key in {"root", "mid_0", "mid_1", "target_0"}
        return actual_get(key)

    monkeypatch.setattr(router.registry, "get", bounded)
    result = graph.lookup_bounded_paths(
        router, ALIASES[0], group=GROUP, principal=ACTOR, hops=3,
    )
    assert result.qualified_path_count == 1
    assert seen


def test_late_same_callable_revocation_invalidates_all_earlier_deep_paths():
    router = _router(3, targets=2)
    graph = _index(router)
    revoked = False

    def health(tool, _endpoint):
        nonlocal revoked
        if tool.key == "target_1":
            revoked = True
        return not (revoked and tool.key == "mid_0")

    router.planner.availability_predicate = health
    with pytest.raises(
        PolicyViolationError,
        match="G5 bounded path eligibility changed during lookup",
    ):
        graph.lookup_bounded_paths(
            router, ALIASES[0], group=GROUP, principal=ACTOR, hops=3,
        )
    assert revoked


@pytest.mark.parametrize("bad_hops", (0, 1, 5, True, 3.5))
def test_expansion_depth_must_be_explicitly_bounded(bad_hops):
    router = _router(3)
    with pytest.raises(ValueError, match="2..4 hops"):
        _index(router).lookup_bounded_paths(
            router, ALIASES[0], group=GROUP, principal=ACTOR, hops=bad_hops,
        )


def test_deep_path_untrusted_query_and_registry_mutation_fail_closed():
    router = _router(3)
    graph = _index(router)
    with pytest.raises(ValueError, match="host-approved query edge"):
        graph.lookup_bounded_paths(
            router, "unreviewed target", group=GROUP, principal=ACTOR,
        )
    router.add_tool(_tool("new_source", output="other.new"))
    with pytest.raises(PolicyViolationError, match="source revision is stale"):
        graph.lookup_bounded_paths(
            router, ALIASES[0], group=GROUP, principal=ACTOR,
        )


def test_deep_path_availability_exception_redacts_private_provider_details():
    router = _router(3)
    graph = _index(router)
    private = "private-health-provider-message-8877"

    def broken(_tool, _endpoint):
        raise RuntimeError(private)

    router.planner.availability_predicate = broken
    with pytest.raises(
        PolicyViolationError, match="G5 bounded path eligibility changed",
    ) as caught:
        graph.lookup_bounded_paths(
            router, ALIASES[0], group=GROUP, principal=ACTOR,
        )
    assert private not in str(caught.value)
    assert caught.value.__suppress_context__


def test_two_hop_new_general_depth_agrees_with_existing_source_evidence():
    router = _router(2)
    graph = _index(router)
    legacy = graph.lookup_two_hop(
        router, ALIASES[0], group=GROUP, principal=ACTOR,
    )
    flexible = graph.lookup_bounded_paths(
        router, ALIASES[0], group=GROUP, principal=ACTOR, hops=2,
    )
    assert legacy.qualified_path_count == flexible.qualified_path_count == 1
    assert legacy.candidates[0].route_ids == flexible.candidates[0].route_ids
    assert (
        legacy.candidates[0].route_fingerprints
        == flexible.candidates[0].route_fingerprints
    )
    assert (
        legacy.candidates[0].root_to_intermediate,
        legacy.candidates[0].intermediate_to_target,
    ) == flexible.candidates[0].parameter_bindings


@pytest.mark.parametrize("fanout", ("denied_targets", "unavailable_predecessors"))
def test_bounded_graph_budget_counts_rejected_candidate_probes(
    fanout, monkeypatch,
):
    """Ineligible posting/edge fan-out must not cause unbounded source reads.

    The 256 visit cap includes every examined target and predecessor, even
    when live health says the route is unavailable and no path qualifies.
    """
    if fanout == "denied_targets":
        router = _router(3, targets=270)
    else:
        router = _router(3)
        for i in range(270):
            router.add_tool(_tool(
                f"alternate_{i:03d}",
                requires="billing.id_0", output="billing.id_1",
            ))
    graph = _index(router)
    touched: list[str] = []

    def health(tool, _endpoint):
        touched.append(tool.key)
        if fanout == "denied_targets":
            return not tool.key.startswith("target_")
        return not tool.key.startswith("alternate_")

    router.planner.availability_predicate = health
    with pytest.raises(
        PolicyViolationError,
        match="G5 bounded path eligibility changed during lookup",
    ) as caught:
        graph.lookup_bounded_paths(
            router, ALIASES[0], group=GROUP, principal=ACTOR, hops=3,
        )
    assert touched
    # A live endpoint may be rechecked as the consumer and producer of
    # multiple edges. The 256 budget bounds newly examined indexed
    # targets/predecessors, not repeat eligibility checks of the same route.
    assert len(touched) <= 256 + 8
    assert caught.value.__suppress_context__
    assert router.registry.version == graph.field_index.registry_version
