"""Synthetic one-hop graph constraints; independent task E2 remains unqualified."""
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
from schemarouter.errors import PolicyViolationError
from scripts.research_authorized_native_graph_edges_g1 import (
    DeclaredQueryInputLink,
    retrieve_authorized_dependency_hints_g1,
)

ANALYST = PrincipalContext(subject="research-analyst", roles=("analyst",))
VIEWER = PrincipalContext(subject="research-viewer", roles=("viewer",))
LINK = DeclaredQueryInputLink(
    query_aliases=("결정구조 조회", "結晶構造を検索", "look up crystal structure"),
    target_route_id="structure.read",
    target_output_semantic_id="resource.structure_id",
    parameter_name="material_id",
    input_semantic_id="resource.material_id",
)


def _make_router(
    *,
    wrong_type: bool = False,
    target_extra_required: bool = False,
    target_input_type: str = "string",
    producer_pattern: bool = False,
    consumer_enum: bool = False,
    target_location: str = "argument",
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
                operation="materials.read", roles_any=("viewer",),
                hidden_fields=("material_id",),
            ),
        ),
    ))
    producer = FieldSpec(
        name="material_id", semantic_id="resource.material_id",
        json_schema=(
            {"type": "string", "pattern": "^MP-"} if producer_pattern
            else {"type": "integer" if wrong_type else "string"}
        ),
    )
    router.add_tool(ToolSpec(
        name="materials", endpoints=[EndpointSpec(
            name="read", read_only=True, output_fields=[
                producer,
                FieldSpec(
                    name="formula", semantic_id="material.formula",
                    json_schema={"type": "string"},
                ),
            ],
        )],
    ))
    router.add_tool(ToolSpec(
        name="structure", endpoints=[EndpointSpec(
            name="read", read_only=True,
            parameters=[
                ParameterSpec(
                    name="material_id", required=True,
                    location=target_location,
                    json_schema=(
                        {"type": "string", "enum": ["known"]}
                        if consumer_enum else {"type": target_input_type}
                    ),
                ),
                *(
                    [ParameterSpec(
                        name="api_key", required=True,
                        json_schema={"type": "string"},
                    )] if target_extra_required else []
                ),
            ],
            output_fields=[FieldSpec(
                name="structure_id", semantic_id="resource.structure_id",
                json_schema={"type": "string"},
            )],
        )],
    ))
    router.add_tool(ToolSpec(
        name="private", endpoints=[EndpointSpec(
            name="read", read_only=True, output_fields=[producer],
        )],
    ))
    router.add_tool(ToolSpec(
        name="wrong_semantic", endpoints=[EndpointSpec(
            name="read", read_only=True, output_fields=[FieldSpec(
                name="material_alias", semantic_id="resource.other",
                json_schema={"type": "string"},
            )],
        )],
    ))
    router.add_tool(ToolSpec(
        name="mutating", endpoints=[EndpointSpec(
            name="read", read_only=False, destructive=True,
            output_fields=[producer],
        )],
    ))
    return router


@pytest.mark.parametrize("query", LINK.query_aliases)
def test_real_native_graph_edge_requires_authorized_semantic_and_type(query):
    hints = retrieve_authorized_dependency_hints_g1(
        _make_router(), query, principal=ANALYST, link=LINK,
    )
    assert len(hints) == 1
    assert hints[0].producer_route_id == "materials.read"
    assert hints[0].consumer_route_id == "structure.read"
    assert hints[0].producer_output_field == "material_id"
    assert hints[0].consumer_input_parameter == "material_id"
    assert hints[0].semantic_id == "resource.material_id"


def test_hidden_field_does_not_produce_graph_edge():
    hints = retrieve_authorized_dependency_hints_g1(
        _make_router(), LINK.query_aliases[0], principal=VIEWER, link=LINK,
    )
    assert hints == ()


@pytest.mark.parametrize("kwargs", (
    {"wrong_type": True},
    {"target_extra_required": True},
    {"target_input_type": "number"},
    {"producer_pattern": True},
    {"consumer_enum": True},
    {"target_location": "header"},
))
def test_incompatible_or_unbound_consumer_does_not_fake_edge(kwargs):
    assert retrieve_authorized_dependency_hints_g1(
        _make_router(**kwargs), LINK.query_aliases[0],
        principal=ANALYST, link=LINK,
    ) == ()


def test_declared_target_and_query_are_not_guessed_from_name_similarity():
    router = _make_router()
    with pytest.raises(ValueError, match="no declared route intent"):
        retrieve_authorized_dependency_hints_g1(
            router, "crystal structure extra guessed words",
            principal=ANALYST, link=LINK,
        )
    assert retrieve_authorized_dependency_hints_g1(
        router, LINK.query_aliases[0], principal=ANALYST,
        link=DeclaredQueryInputLink(
            query_aliases=LINK.query_aliases,
            target_route_id="missing.read",
            target_output_semantic_id="resource.structure_id",
            parameter_name="material_id",
            input_semantic_id="resource.material_id",
        ),
    ) == ()


def test_explicit_availability_is_not_overridden():
    router = _make_router()
    router.planner.availability_predicate = lambda tool, endpoint: tool.name != "materials"
    assert retrieve_authorized_dependency_hints_g1(
        router, LINK.query_aliases[0], principal=ANALYST, link=LINK,
    ) == ()


def test_graph_preview_never_executes_or_calls_planner(monkeypatch):
    router = _make_router()

    def forbidden(*_args, **_kwargs):
        raise AssertionError("graph preview must never plan/execute")

    monkeypatch.setattr(router, "plan", forbidden)
    monkeypatch.setattr(router, "execute", forbidden)
    assert retrieve_authorized_dependency_hints_g1(
        router, LINK.query_aliases[0], principal=ANALYST, link=LINK,
    )


def test_stale_policy_rejected_before_disclosing_graph_hints(monkeypatch):
    router = _make_router()
    original = router._check_retrieval_authority_witness

    def corrupt(witness):
        router.authorization_policy = AuthorizationPolicy(default_effect="deny")
        return original(witness)

    monkeypatch.setattr(router, "_check_retrieval_authority_witness", corrupt)
    with pytest.raises(PolicyViolationError, match="authority changed"):
        retrieve_authorized_dependency_hints_g1(
            router, LINK.query_aliases[0], principal=ANALYST, link=LINK,
        )


@pytest.mark.parametrize("bad_k", (0, 1, 6, True, "5"))
def test_strict_k_rejects_tuning(bad_k):
    with pytest.raises(ValueError, match="strict fixed K5"):
        retrieve_authorized_dependency_hints_g1(
            _make_router(), LINK.query_aliases[0],
            principal=ANALYST, link=LINK, k=bad_k,
        )


def test_invalid_alias_declarations_rejected():
    with pytest.raises(ValueError, match="invalid declared"):
        DeclaredQueryInputLink(
            query_aliases=("x", "x"), target_route_id="structure.read",
            target_output_semantic_id="resource.structure_id",
            parameter_name="material_id", input_semantic_id="resource.material_id",
        )


def test_graph_more_than_k5_proven_edges_is_rejected_not_truncated():
    router = _make_router()
    for i in range(5):
        router.add_tool(ToolSpec(
            name=f"secondary_{i}", endpoints=[EndpointSpec(
                name="read", read_only=True,
                output_fields=[FieldSpec(
                    name="resource_material_id",
                    semantic_id="resource.material_id",
                    json_schema={"type": "string"},
                )],
            )],
        ))
    with pytest.raises(ValueError, match="predecessor K budget exceeded"):
        retrieve_authorized_dependency_hints_g1(
            router, LINK.query_aliases[0], principal=ANALYST, link=LINK,
        )


def test_denied_consumer_does_not_reveal_graph_predecessors():
    router = _make_router()
    router.authorization_policy = AuthorizationPolicy(default_effect="deny")
    assert retrieve_authorized_dependency_hints_g1(
        router, LINK.query_aliases[0], principal=ANALYST, link=LINK,
    ) == ()
