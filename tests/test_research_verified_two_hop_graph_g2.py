"""Two-edge typed graph candidates are NOT autonomous execution plans."""
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
from scripts.research_authorized_native_graph_edges_g1 import DeclaredQueryInputLink
from scripts.research_verified_two_hop_graph_g2 import (
    DeclaredTwoHopGraphIntent,
    retrieve_authorized_two_hop_hints_g2,
)

ANALYST = PrincipalContext(subject="synthetic-analyst", roles=("analyst",))
VIEWER = PrincipalContext(subject="synthetic-viewer", roles=("viewer",))
ALIASES = ("탄성계수와 강도 조회", "ヤング率と強度を検索", "read modulus and strength")
MATERIAL_ID = FieldSpec(
    name="material_id", semantic_id="resource.material_id",
    json_schema={"type": "string"},
)
STRUCTURE_ID = FieldSpec(
    name="structure_id", semantic_id="resource.structure_id",
    json_schema={"type": "string"},
)


def _tool(
    name: str, endpoint: EndpointSpec, *, provider: str | None = "synthetic",
) -> ToolSpec:
    return ToolSpec(
        name=name, provider=provider,
        source_type="materials_data", license="CC-BY-4.0",
        endpoints=[endpoint],
    )


def _router(
    *, wrong_middle_input: bool = False, wrong_final_input: bool = False,
    extra_middle_required: bool = False, hidden_material: bool = True,
    require_source_input: bool = False, mutate_middle: bool = False,
    missing_source_provenance: bool = False, omit_final_field: bool = False,
    wrong_final_field_type: bool = False, cyclic_final_output: bool = False,
) -> SchemaRouter:
    policy = AuthorizationPolicy(
        default_effect="deny",
        rules=(
            AuthorizationRule(
                effect="deny", operation="private.read",
                roles_any=("analyst", "viewer"),
            ),
            AuthorizationRule(
                effect="allow", operation="*.read",
                roles_any=("analyst", "viewer"),
            ),
        ),
        data_rules=(
            DataScopeRule(
                operation="materials.read", roles_any=("viewer",),
                hidden_fields=("material_id",) if hidden_material else (),
            ),
        ),
    )
    router = SchemaRouter(authorization_policy=policy)
    router.add_tool(_tool("materials", EndpointSpec(
        name="read", read_only=True,
        parameters=(
            [ParameterSpec(name="search", required=True, json_schema={"type": "string"})]
            if require_source_input else []
        ),
        output_fields=[
            MATERIAL_ID,
            FieldSpec(name="formula", semantic_id="material.formula",
                      json_schema={"type": "string"}),
        ],
    ), provider=None if missing_source_provenance else "synthetic"))
    router.add_tool(_tool("structure", EndpointSpec(
        name="read", read_only=not mutate_middle, destructive=mutate_middle,
        parameters=[
            ParameterSpec(
                name="material_id", required=True,
                json_schema={"type": "number" if wrong_middle_input else "string"},
            ),
            *(
                [ParameterSpec(name="extra", required=True,
                               json_schema={"type": "string"})]
                if extra_middle_required else []
            ),
        ],
        output_fields=[STRUCTURE_ID],
    )))
    router.add_tool(_tool("properties", EndpointSpec(
        name="read", read_only=True,
        parameters=[ParameterSpec(
            name="structure_id", required=True,
            json_schema={"type": "integer" if wrong_final_input else "string"},
        )],
        output_fields=[
            FieldSpec(name="modulus", semantic_id="mechanics.elastic_modulus",
                      json_schema={"type": "number"}),
            *(
                [] if omit_final_field else
                [FieldSpec(name="tensile", semantic_id="mechanics.tensile",
                           json_schema={
                               "type": "string" if wrong_final_field_type else "number"
                           })]
            ),
            *([MATERIAL_ID] if cyclic_final_output else []),
        ],
    )))
    router.add_tool(_tool("private", EndpointSpec(
        name="read", read_only=True, output_fields=[MATERIAL_ID],
    )))
    router.add_tool(_tool("wrong_id", EndpointSpec(
        name="read", read_only=True, output_fields=[FieldSpec(
            name="material_id", semantic_id="resource.other_id",
            json_schema={"type": "string"},
        )],
    )))
    return router


def _declaration(router: SchemaRouter) -> DeclaredTwoHopGraphIntent:
    return DeclaredTwoHopGraphIntent(
        first=DeclaredQueryInputLink(
            query_aliases=ALIASES,
            target_route_id="structure.read",
            target_output_semantic_id="resource.structure_id",
            parameter_name="material_id",
            input_semantic_id="resource.material_id",
        ),
        second=DeclaredQueryInputLink(
            query_aliases=ALIASES,
            target_route_id="properties.read",
            target_output_semantic_id="mechanics.elastic_modulus",
            parameter_name="structure_id",
            input_semantic_id="resource.structure_id",
        ),
        required_final_fields=(
            CapabilityFieldContract(
                semantic_id="mechanics.elastic_modulus",
                json_schema={"type": "number"},
            ),
            CapabilityFieldContract(
                semantic_id="mechanics.tensile",
                json_schema={"type": "number"},
            ),
        ),
        first_consumer_fingerprint=router.registry.get(
            "structure"
        ).endpoint("read").fingerprint,
        second_consumer_fingerprint=router.registry.get(
            "properties"
        ).endpoint("read").fingerprint,
    )


@pytest.mark.parametrize("query", ALIASES)
def test_two_real_graph_edges_and_complete_final_fields(query: str) -> None:
    router = _router()
    results = retrieve_authorized_two_hop_hints_g2(
        router, query, principal=ANALYST, declaration=_declaration(router),
    )
    assert len(results) == 1
    item = results[0]
    assert len(item.authorized_snapshot_id) == 64
    assert item.source_to_intermediate.producer_route_id == "materials.read"
    assert item.source_to_intermediate.consumer_route_id == "structure.read"
    assert item.source_to_intermediate.producer_output_field == "material_id"
    assert item.source_to_intermediate.consumer_input_parameter == "material_id"
    assert item.intermediate_to_target.producer_route_id == "structure.read"
    assert item.intermediate_to_target.consumer_route_id == "properties.read"
    assert item.intermediate_to_target.producer_output_field == "structure_id"
    assert item.intermediate_to_target.consumer_input_parameter == "structure_id"
    assert item.verified_final_semantics == (
        "mechanics.elastic_modulus", "mechanics.tensile",
    )
    assert retrieve_authorized_two_hop_hints_g2(
        router, query, principal=ANALYST, declaration=_declaration(router),
    ) == results


def test_hidden_field_and_denied_predecessor_are_not_in_graph():
    router = _router()
    assert retrieve_authorized_two_hop_hints_g2(
        router, ALIASES[0], principal=VIEWER, declaration=_declaration(router),
    ) == ()
    router.authorization_policy = AuthorizationPolicy(default_effect="deny")
    assert retrieve_authorized_two_hop_hints_g2(
        router, ALIASES[0], principal=ANALYST, declaration=_declaration(router),
    ) == ()


@pytest.mark.parametrize("fixture_change", (
    {"wrong_middle_input": True},
    {"wrong_final_input": True},
    {"extra_middle_required": True},
    {"require_source_input": True},
    {"mutate_middle": True},
    {"missing_source_provenance": True},
    {"omit_final_field": True},
    {"wrong_final_field_type": True},
))
def test_no_unproven_graph_composition(fixture_change) -> None:
    router = _router(**fixture_change)
    assert retrieve_authorized_two_hop_hints_g2(
        router, ALIASES[0], principal=ANALYST, declaration=_declaration(router),
    ) == ()


def test_query_is_exactly_declared_and_no_names_are_inferred():
    router = _router()
    for query in ("read modulus", "find material then call properties", ""):
        with pytest.raises(ValueError, match="no declared intent"):
            retrieve_authorized_two_hop_hints_g2(
                router, query, principal=ANALYST, declaration=_declaration(router),
            )


@pytest.mark.parametrize("k,hops", (
    (1, 2), (6, 2), (True, 2), (5, 1), (5, 3), (5, True),
))
def test_strict_k_and_hops_reject_budget_bypass(k, hops):
    router = _router()
    with pytest.raises(ValueError, match="strict K5|exactly two"):
        retrieve_authorized_two_hop_hints_g2(
            router, ALIASES[0], principal=ANALYST,
            declaration=_declaration(router), k=k, max_hops=hops,
        )


def test_pinned_registered_endpoint_fingerprint_prevents_stale_ontology():
    router = _router()
    declaration = _declaration(router)
    bad = DeclaredTwoHopGraphIntent(
        first=declaration.first,
        second=declaration.second,
        required_final_fields=declaration.required_final_fields,
        first_consumer_fingerprint="0" * 64,
        second_consumer_fingerprint=declaration.second_consumer_fingerprint,
    )
    with pytest.raises(ValueError, match="stale declared graph source"):
        retrieve_authorized_two_hop_hints_g2(
            router, ALIASES[0], principal=ANALYST, declaration=bad,
        )


def test_rejects_fake_two_hop_relation_and_missing_semantic_output():
    router = _router()
    old = _declaration(router)
    with pytest.raises(ValueError, match="invalid pinned"):
        DeclaredTwoHopGraphIntent(
            first=old.first,
            second=DeclaredQueryInputLink(
                query_aliases=ALIASES,
                target_route_id="properties.read",
                target_output_semantic_id="mechanics.elastic_modulus",
                parameter_name="structure_id",
                input_semantic_id="resource.unrelated_id",
            ),
            required_final_fields=old.required_final_fields,
            first_consumer_fingerprint=old.first_consumer_fingerprint,
            second_consumer_fingerprint=old.second_consumer_fingerprint,
        )


def test_source_policy_churn_before_publication_fails_closed(monkeypatch):
    router = _router()
    original = router._check_retrieval_authority_witness

    def drift(witness):
        router.authorization_policy = AuthorizationPolicy(default_effect="deny")
        return original(witness)

    monkeypatch.setattr(router, "_check_retrieval_authority_witness", drift)
    with pytest.raises(PolicyViolationError, match="authority changed"):
        retrieve_authorized_two_hop_hints_g2(
            router, ALIASES[0], principal=ANALYST, declaration=_declaration(router),
        )


def test_no_invoker_agent_or_execution(monkeypatch):
    router = _router()

    def forbidden(*_args, **_kwargs):
        raise AssertionError("typed graph retrieval must never plan or execute")

    monkeypatch.setattr(router, "plan", forbidden)
    monkeypatch.setattr(router, "execute", forbidden)
    assert retrieve_authorized_two_hop_hints_g2(
        router, ALIASES[0], principal=ANALYST, declaration=_declaration(router),
    )


def test_composite_join_is_not_claimed_from_arbitrary_field_union():
    # Extra required inputs at the middle endpoint fail even if another
    # unrelated tool happens to produce a same-named output.
    bad_router = _router(extra_middle_required=True)
    assert retrieve_authorized_two_hop_hints_g2(
        bad_router, ALIASES[0], principal=ANALYST,
        declaration=_declaration(bad_router),
    ) == ()


def test_two_hop_dependency_cycle_fails_closed():
    router = _router(cyclic_final_output=True)
    with pytest.raises(ValueError, match="dependency cycle"):
        retrieve_authorized_two_hop_hints_g2(
            router, ALIASES[0], principal=ANALYST, declaration=_declaration(router),
        )


def test_more_than_k5_complete_predecessors_fail_closed():
    router = _router()
    for i in range(5):
        router.add_tool(_tool(f"material_candidate_{i}", EndpointSpec(
            name="read", read_only=True,
            output_fields=[MATERIAL_ID],
        )))
    with pytest.raises(ValueError, match="complete graph path K budget"):
        retrieve_authorized_two_hop_hints_g2(
            router, ALIASES[0], principal=ANALYST, declaration=_declaration(router),
        )
