"""G2 declared and source-pinned two-hop graph path regressions (synthetic)."""
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
from scripts.research_verified_graph_paths_g2 import (
    DeclaredGraphGoalG2,
    DeclaredInputBindingG2,
    retrieve_verified_graph_paths_g2,
)

ANALYST = PrincipalContext(subject="graph-analyst", roles=("analyst",))
VIEWER = PrincipalContext(subject="graph-viewer", roles=("viewer",))
ALIASES = ("결정 구조의 물성", "結晶構造の物性", "properties of crystal structure")


def _field(
    name: str, semantic_id: str, schema_type: str = "string",
    *, identifier: bool = False, unit: str | None = None,
) -> FieldSpec:
    return FieldSpec(
        name=name,
        semantic_id=semantic_id,
        identifier=identifier,
        json_schema={"type": schema_type},
        unit=unit,
    )


def _router(
    *, wrong_middle_type: bool = False, extra_input: bool = False,
    wrong_middle_output: bool = False, root_identifier: bool = True,
    property_strength: bool = True, omit_license: bool = False,
) -> SchemaRouter:
    router = SchemaRouter(authorization_policy=AuthorizationPolicy(
        default_effect="deny",
        rules=(
            AuthorizationRule(
                effect="deny", operation="private.read", roles_any=("analyst", "viewer"),
            ),
            AuthorizationRule(
                effect="allow", operation="*.read", roles_any=("analyst", "viewer"),
            ),
        ),
        data_rules=(
            DataScopeRule(
                operation="find.read", roles_any=("viewer",),
                hidden_fields=("material_id",),
            ),
            DataScopeRule(
                operation="property.read", roles_any=("viewer",),
                hidden_fields=("tensile_strength",),
            ),
        ),
    ))
    source_type = "materials_data"
    license_id = None if omit_license else "CC-BY-4.0"

    def register(
        name: str, *, parameters: list[ParameterSpec] | None = None,
        fields: list[FieldSpec],
        read_only: bool = True, license_override: str | None = None,
    ) -> None:
        router.add_tool(ToolSpec(
            name=name,
            source_type=source_type,
            license=license_id if license_override is None else license_override,
            endpoints=[EndpointSpec(
                name="read", read_only=read_only,
                destructive=not read_only,
                parameters=parameters or [],
                output_fields=fields,
            )],
        ))

    register("find", fields=[
        _field("material_id", "resource.material_id", identifier=root_identifier),
        _field("formula", "chemistry.formula"),
    ])
    register("structure", parameters=[
        ParameterSpec(
            name="material_id", required=True,
            json_schema={"type": "integer" if wrong_middle_type else "string"},
        ),
        *([ParameterSpec(
            name="secret_extra", required=True,
            json_schema={"type": "string"},
        )] if extra_input else []),
    ], fields=[
        _field(
            "structure_id",
            "resource.wrong_structure" if wrong_middle_output
            else "resource.structure_id",
            identifier=True,
        ),
    ])
    fields = [_field("elastic_modulus", "property.elastic_modulus", "number", unit="GPa")]
    if property_strength:
        fields.append(_field(
            "tensile_strength", "property.tensile_strength", "number", unit="MPa",
        ))
    register("property", parameters=[
        ParameterSpec(name="structure_id", required=True, json_schema={"type": "string"}),
    ], fields=fields)
    register("private", fields=[
        _field("material_id", "resource.material_id", identifier=True),
    ])
    register("mutating", fields=[
        _field("material_id", "resource.material_id", identifier=True),
    ], read_only=False)
    register("wrong_semantics", fields=[
        _field("material_id", "resource.different_material", identifier=True),
    ])
    return router


def _goal(
    router: SchemaRouter, *,
    wrong_input_semantic: bool = False,
    corrupt_fingerprint: bool = False,
    target_aliases: tuple[str, ...] = ALIASES,
    wrong_target_unit: bool = False,
) -> DeclaredGraphGoalG2:
    structure_fp = router.registry.get("structure").endpoint("read").fingerprint
    property_fp = router.registry.get("property").endpoint("read").fingerprint
    return DeclaredGraphGoalG2(
        aliases=target_aliases,
        target_route_id="property.read",
        required_outputs=(
            CapabilityFieldContract(
                semantic_id="property.elastic_modulus",
                json_schema={"type": "number"},
                unit="MPa" if wrong_target_unit else "GPa",
            ),
            CapabilityFieldContract(
                semantic_id="property.tensile_strength",
                json_schema={"type": "number"}, unit="MPa",
            ),
        ),
        bindings=(
            DeclaredInputBindingG2(
                route_id="structure.read",
                parameter_name="material_id",
                semantic_id=(
                    "resource.fake_id" if wrong_input_semantic
                    else "resource.material_id"
                ),
                expected_endpoint_fingerprint=(
                    "stale:sha" if corrupt_fingerprint else structure_fp
                ),
            ),
            DeclaredInputBindingG2(
                route_id="property.read",
                parameter_name="structure_id",
                semantic_id="resource.structure_id",
                expected_endpoint_fingerprint=property_fp,
            ),
        ),
    )


@pytest.mark.parametrize("query", ALIASES)
def test_native_two_hop_chain_has_authorized_typed_bindings_and_receipt(query):
    router = _router()
    result = retrieve_verified_graph_paths_g2(
        router, query, principal=ANALYST, goal=_goal(router),
    )
    assert len(result) == 1
    hint = result[0]
    assert hint.route_ids == ("find.read", "structure.read", "property.read")
    assert [(e.producer_output_field, e.consumer_input_parameter, e.semantic_id)
            for e in hint.edges] == [
        ("material_id", "material_id", "resource.material_id"),
        ("structure_id", "structure_id", "resource.structure_id"),
    ]
    assert hint.target_output_fields == ("elastic_modulus", "tensile_strength")
    assert len(hint.scoped_snapshot_id) == 64
    assert result == retrieve_verified_graph_paths_g2(
        router, query, principal=ANALYST, goal=_goal(router),
    )


@pytest.mark.parametrize("kwargs", [
    {"wrong_middle_type": True},
    {"extra_input": True},
    {"wrong_middle_output": True},
    {"root_identifier": False},
    {"property_strength": False},
    {"omit_license": True},
])
def test_incompatible_or_incomplete_registered_graph_never_fabricates_path(kwargs):
    router = _router(**kwargs)
    assert retrieve_verified_graph_paths_g2(
        router, ALIASES[0], principal=ANALYST, goal=_goal(router),
    ) == ()


def test_hidden_required_identifier_and_output_field_are_not_promoted():
    router = _router()
    assert retrieve_verified_graph_paths_g2(
        router, ALIASES[0], principal=VIEWER, goal=_goal(router),
    ) == ()


def test_type_source_fingerprint_and_target_unit_are_explicit_requirements():
    router = _router()
    with pytest.raises(ValueError, match="binding source is stale"):
        retrieve_verified_graph_paths_g2(
            router, ALIASES[0], principal=ANALYST,
            goal=_goal(router, corrupt_fingerprint=True),
        )
    assert retrieve_verified_graph_paths_g2(
        router, ALIASES[0], principal=ANALYST,
        goal=_goal(router, wrong_input_semantic=True),
    ) == ()
    assert retrieve_verified_graph_paths_g2(
        router, ALIASES[0], principal=ANALYST,
        goal=_goal(router, wrong_target_unit=True),
    ) == ()


def test_no_automatic_partial_path_when_max_hops_one():
    router = _router()
    assert retrieve_verified_graph_paths_g2(
        router, ALIASES[0], principal=ANALYST,
        goal=_goal(router), max_hops=1,
    ) == ()


def test_no_query_guessing_or_invalid_graph_budget_or_invalid_metadata():
    router = _router()
    goal = _goal(router)
    with pytest.raises(ValueError, match="query-to-graph"):
        retrieve_verified_graph_paths_g2(
            router, "get properties plus unrelated words",
            principal=ANALYST, goal=goal,
        )
    for kwargs in ({"k": 2}, {"k": True}, {"max_hops": 3},
                   {"max_hops": 1.0}):
        with pytest.raises(ValueError):
            retrieve_verified_graph_paths_g2(
                router, ALIASES[0], principal=ANALYST, goal=goal, **kwargs,
            )
    with pytest.raises(ValueError, match="invalid trusted input"):
        DeclaredInputBindingG2(
            route_id="structure.read", parameter_name="material_id",
            semantic_id="resource.material_id",
            expected_endpoint_fingerprint="",
        )
    with pytest.raises(ValueError, match="invalid bounded declared"):
        DeclaredGraphGoalG2(
            aliases=(), target_route_id=goal.target_route_id,
            required_outputs=goal.required_outputs, bindings=goal.bindings,
        )


def test_denied_target_returns_no_metadata_and_no_execution(monkeypatch):
    router = _router()
    goal = _goal(router)
    def forbidden(*_args, **_kwargs):
        raise AssertionError("graph hints cannot call an agent or executor")
    monkeypatch.setattr(router, "plan", forbidden)
    monkeypatch.setattr(router, "execute", forbidden)
    assert retrieve_verified_graph_paths_g2(
        router, ALIASES[0], principal=ANALYST, goal=goal,
    )
    router.authorization_policy = AuthorizationPolicy(default_effect="deny")
    assert retrieve_verified_graph_paths_g2(
        router, ALIASES[0], principal=ANALYST, goal=goal,
    ) == ()


def test_source_or_policy_churn_is_detected_before_publication(monkeypatch):
    router = _router()
    original = router._check_retrieval_authority_witness
    def corrupt(witness):
        router.authorization_policy = AuthorizationPolicy(default_effect="deny")
        return original(witness)
    monkeypatch.setattr(router, "_check_retrieval_authority_witness", corrupt)
    with pytest.raises(PolicyViolationError, match="authority changed"):
        retrieve_verified_graph_paths_g2(
            router, ALIASES[0], principal=ANALYST, goal=_goal(router),
        )


def test_over_k_verified_graph_paths_fail_closed():
    router = _router()
    for i in range(5):
        router.add_tool(ToolSpec(
            name=f"alternate_{i}", source_type="materials_data",
            license="CC-BY-4.0",
            endpoints=[EndpointSpec(
                name="read", read_only=True, output_fields=[
                    _field("material_id", "resource.material_id", identifier=True),
                ],
            )],
        ))
    with pytest.raises(ValueError, match="verified-path K budget exceeded"):
        retrieve_verified_graph_paths_g2(
            router, ALIASES[0], principal=ANALYST, goal=_goal(router),
        )
