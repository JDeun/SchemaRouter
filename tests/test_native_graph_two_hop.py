"""#1560: source-pinned, authorization-scoped G5 two-hop E0 (no executor)."""
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

ACTOR = PrincipalContext(subject="researcher", roles=("reader",))
ALIASES = ("case status", "문의 상태", "問い合わせ状態")
GROUP = NativeDeclaredFieldGroup(
    aliases=ALIASES,
    required_fields=(CapabilityFieldContract(
        semantic_id="crm.status", json_schema={"type": "string"},
    ),),
    source_type="crm",
    license="reviewed",
)


def _node(
    name: str,
    *,
    input_name: str | None = None,
    input_semantic: str | None = None,
    input_type: str = "string",
    output_name: str,
    output_semantic: str,
    output_type: str = "string",
    identifier: bool = False,
) -> ToolSpec:
    parameters = (
        [ParameterSpec(
            name=input_name, semantic_id=input_semantic,
            required=True, json_schema={"type": input_type},
        )]
        if input_name is not None else []
    )
    return ToolSpec(
        name=name, source_type="crm", license="reviewed",
        endpoints=[EndpointSpec(
            name="read", read_only=True, parameters=parameters,
            input_schema=(
                {"type": "object",
                 "properties": {input_name: {"type": input_type}},
                 "required": [input_name]}
                if input_name is not None else {}
            ),
            output_fields=[FieldSpec(
                name=output_name, semantic_id=output_semantic,
                identifier=identifier, json_schema={"type": output_type},
            )],
        )],
    )


def _router(
    *,
    n_targets: int = 1,
    mid_output_type: str = "string",
    target_input_type: str = "string",
    root_output_type: str = "string",
    hidden_intermediate: bool = False,
    deny_intermediate: bool = False,
    noise: int = 0,
) -> SchemaRouter:
    policy = AuthorizationPolicy(
        default_effect="deny",
        rules=(
            ((AuthorizationRule(
                effect="deny", operation="intermediate.read",
                roles_any=("reader",),
            ),) if deny_intermediate else ())
            + (AuthorizationRule(
                effect="allow", operation="*.read",
                roles_any=("reader",),
            ),)
        ),
        data_rules=(DataScopeRule(
            operation="intermediate.read",
            roles_any=("reader",),
            hidden_fields=("case_id",),
        ),) if hidden_intermediate else (),
    )
    router = SchemaRouter(authorization_policy=policy)
    router.add_tool(_node(
        "root", output_name="contact_id",
        output_semantic="crm.contact_id", output_type=root_output_type,
        identifier=True,
    ))
    router.add_tool(_node(
        "intermediate", input_name="contact_id",
        input_semantic="crm.contact_id", output_name="case_id",
        output_semantic="crm.case_id", output_type=mid_output_type,
        identifier=True,
    ))
    for idx in range(n_targets):
        router.add_tool(_node(
            f"target_{idx}", input_name="case_id",
            input_semantic="crm.case_id", input_type=target_input_type,
            output_name="status", output_semantic="crm.status",
        ))
    for idx in range(noise):
        router.add_tool(_node(
            f"noise_{idx}", output_name="unrelated",
            output_semantic="science.unrelated",
        ))
    return router


def _index(router: SchemaRouter) -> NativeSchemaGraphIndex:
    return NativeSchemaGraphIndex.build(
        NativeSchemaPostingIndex.build(router.registry),
    )


@pytest.mark.parametrize("query", ALIASES)
def test_two_hop_returns_original_source_typed_bindings_and_no_execution(query):
    router = _router(noise=30)
    index = _index(router)
    assert index.graph.predecessors("intermediate.read") == ("root.read",)
    assert index.graph.predecessors("target_0.read") == (
        "intermediate.read",
    )
    result = index.lookup_two_hop(router, query, group=GROUP, principal=ACTOR)
    assert result.status == "complete"
    assert result.qualified_path_count == 1
    assert len(result.candidates) == 1
    item = result.candidates[0]
    assert item.route_ids == (
        "root.read", "intermediate.read", "target_0.read",
    )
    assert item.root_to_intermediate == (("contact_id", "contact_id"),)
    assert item.intermediate_to_target == (("case_id", "case_id"),)
    assert item.target_output_fields == ("status",)
    assert item.source_root_parameters == ()
    assert len(item.route_fingerprints) == 3
    assert item.route_fingerprints == tuple(
        index.field_index.route_fingerprints[route]
        for route in item.route_ids
    )
    assert result.executable_authority is False
    assert result.independent_quality_evidence is False
    assert result.calibrated_no_fit is False
    # Existing original one-hop API never promotes the intermediary into
    # an unauthorized root merely because it now has a produced ID.
    one = index.lookup(router, query, group=GROUP, principal=ACTOR)
    assert one.status == "no_proven_hit"


@pytest.mark.parametrize("change", (
    "wrong_root_type", "wrong_middle_output_type",
    "wrong_target_input_type", "denied_middle", "hidden_middle",
))
def test_two_hop_rejects_unproven_typed_source_or_hidden_intermediary(change):
    changes = {
        "wrong_root_type": {"root_output_type": "integer"},
        "wrong_middle_output_type": {"mid_output_type": "integer"},
        "wrong_target_input_type": {"target_input_type": "integer"},
        "denied_middle": {"deny_intermediate": True},
        "hidden_middle": {"hidden_intermediate": True},
    }
    router = _router(**changes[change])
    result = _index(router).lookup_two_hop(
        router, ALIASES[0], group=GROUP, principal=ACTOR,
    )
    assert result.status == "no_proven_hit"
    assert result.qualified_path_count == 0
    assert result.candidates == ()


def test_two_hop_six_authorized_paths_abstain_without_exposing_any_candidate():
    router = _router(n_targets=6)
    result = _index(router).lookup_two_hop(
        router, ALIASES[0], group=GROUP, principal=ACTOR,
    )
    assert result.status == "over_k_unranked"
    assert result.qualified_path_count == 6
    assert result.candidates == ()
    assert result.calibrated_no_fit is False


def test_two_hop_does_not_walk_unrelated_registered_native_routes(monkeypatch):
    router = _router(noise=300)
    index = _index(router)
    real_get = router.registry.get
    visited: list[str] = []

    def bounded(key):
        visited.append(key)
        assert key in {"root", "intermediate", "target_0"}
        return real_get(key)

    monkeypatch.setattr(router.registry, "get", bounded)
    result = index.lookup_two_hop(
        router, ALIASES[0], group=GROUP, principal=ACTOR,
    )
    assert result.qualified_path_count == 1
    assert visited


def test_two_hop_same_callable_late_health_revocation_fails_closed():
    router = _router(n_targets=2)
    index = _index(router)
    disabled = False

    def health(tool, _endpoint):
        nonlocal disabled
        if tool.key == "target_1":
            disabled = True
        return not (disabled and tool.key == "intermediate")

    router.planner.availability_predicate = health
    with pytest.raises(
        PolicyViolationError,
        match="G5 two-hop source eligibility changed during lookup",
    ):
        index.lookup_two_hop(
            router, ALIASES[0], group=GROUP, principal=ACTOR,
        )
    assert disabled
    assert router.registry.version == index.field_index.registry_version


def test_two_hop_wrong_query_k_and_stale_source_fail_closed():
    router = _router()
    index = _index(router)
    for query in ("untrusted alias", "不存在"):
        with pytest.raises(ValueError, match="approved semantic edge"):
            index.lookup_two_hop(router, query, group=GROUP, principal=ACTOR)
    with pytest.raises(ValueError, match="fixed K5"):
        index.lookup_two_hop(
            router, ALIASES[0], group=GROUP, principal=ACTOR, k=7,
        )
    router.add_tool(_node(
        "new", output_name="other", output_semantic="science.other",
    ))
    with pytest.raises(PolicyViolationError, match="source revision is stale"):
        index.lookup_two_hop(
            router, ALIASES[0], group=GROUP, principal=ACTOR,
        )


def test_two_hop_availability_callback_never_leaks_private_error():
    router = _router()
    index = _index(router)
    secret = "hidden-provider-twohop-health-4833"

    def broken(_tool, _endpoint):
        raise RuntimeError(secret)

    router.planner.availability_predicate = broken
    with pytest.raises(
        PolicyViolationError, match="G5 two-hop source eligibility changed",
    ) as caught:
        index.lookup_two_hop(
            router, ALIASES[0], group=GROUP, principal=ACTOR,
        )
    assert secret not in str(caught.value)
    assert caught.value.__suppress_context__
